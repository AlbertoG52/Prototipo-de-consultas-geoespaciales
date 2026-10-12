"""Catálogo de especies con los datos reales de CR-BioLM, por MCP.

Implementa la interfaz `FuenteCatalogo` (services/catalogo.py) con las
herramientas del servidor de CR-BioLM. Todo es L0/L1: no usa el LLM.

    buscar_especies      -> get_species (provisional, ver el método)
    obtener_especie      -> get_species
    construir_respuesta  -> get_species + get_occurrence_points + get_species_map_image
    obtener_ficha        -> get_species + get_occurrence_points + get_species_map_image
    obtener_mapa         -> el mapa en memoria, o lo mismo que construir_respuesta

Mapas: todos vienen de CR-BioLM (el PNG de render_species_map). Si CR-BioLM no
genera mapa para una especie, la respuesta sale sin mapa; el backend nunca
dibuja uno propio.

Antes de armar la respuesta, los datos de cada fuente se validan
(services/validacion_datos.py):

- RR_60: solo se usa lo que corresponde exactamente a la especie pedida; el
  resto se descarta.
- RR_43: con menos de MINIMO_REGISTROS_MAPA registros válidos no se pide ni se
  muestra mapa, y la respuesta lo avisa en `avisos`.
- RR_58: si CR-BioLM no logra consultar GBIF, se reintenta hasta
  GBIF_REINTENTOS veces con una espera entre intentos. Si todos fallan, la
  respuesta sale con los datos del Manual, sin registros ni mapa, y lo avisa.

Se activa con CATALOGO=crbiolm en el .env (ver config.py). Los errores de
conexión con CR-BioLM y el tiempo agotado no se atrapan aquí: los maneja el
servicio de consultas (RR_38) y, más adelante, RR_05. Las excepciones son GBIF
(RR_58, arriba) y el mapa: si la herramienta del mapa falla, la respuesta sale
igual, sin mapa.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from .. import config
from ..schemas.consulta import (
    EspecieCandidata,
    FichaEspecie,
    MapaEspecie,
    RegistroPresencia,
    RespuestaConsulta,
)
from ..tiempo import alcanza_para_esperar
from . import mcp_cliente
from .mcp_cliente import MCPErrorHerramienta, MCPRespuestaInvalida, Sobre
from .validacion_datos import alcanza_para_mapa, misma_especie, punto_valido

logger = logging.getLogger("uvicorn.error")

SIN_DATO = "Sin dato"
FUENTE_GBIF = "GBIF"

# Mapas que se guardan en memoria para servirlos en GET /especies/{id}/mapa sin
# volver a pedirlos a CR-BioLM. Cada PNG pesa unos cientos de KB.
MAPAS_EN_MEMORIA = 64

# Rangos infraespecíficos que el id escribe sin punto ("var", no "var.").
_RANGOS = {"var", "subsp", "f"}


# --- id <-> nombre científico --------------------------------------------------


def a_id(nombre_cientifico: str) -> str:
    """'Quercus costaricensis' -> 'quercus-costaricensis' (formato de ConsultaRequest)."""
    limpio = "".join(c for c in nombre_cientifico.lower() if c.isalnum() or c == " ")
    return "-".join(limpio.split())


def a_nombre(especie_id: str) -> str:
    """'quercus-costaricensis' -> 'Quercus costaricensis' (como lo guarda CR-BioLM)."""
    partes = [f"{p}." if p in _RANGOS else p for p in especie_id.split("-")]
    return " ".join(partes).capitalize()


# --- catálogo -------------------------------------------------------------------


@dataclass(frozen=True)
class _Mapa:
    png: bytes
    capas: list[str]
    puntos: int
    advertencia: str | None


@dataclass(frozen=True)
class _Ocurrencias:
    """Los registros de GBIF de una especie, ya validados (RR_60)."""

    sobre: Sobre | None  # None: GBIF no respondió en ningún intento (RR_58)
    registros: list[RegistroPresencia]
    # Registros válidos en total. Puede ser mayor que len(registros): CR-BioLM
    # cuenta todos pero entrega como máximo 500 puntos.
    total: int
    intentos: int


@dataclass(frozen=True)
class _Datos:
    """Todo lo que se sabe de una especie, validado, listo para armar la respuesta."""

    manual: Sobre
    ocurrencias: _Ocurrencias
    mapa: _Mapa | None
    avisos: list[str]

    @property
    def ficha(self) -> dict[str, Any]:
        return self.manual.valor

    @property
    def especie(self) -> str:
        return str(self.ficha["species"])

    def fuentes(self) -> list[str]:
        sobres = [self.manual]
        if self.ocurrencias.sobre is not None:
            sobres.append(self.ocurrencias.sobre)
        return _fuentes(*sobres)

    def mapa_especie(self) -> MapaEspecie | None:
        """Lo que la respuesta dice del mapa; la imagen se pide aparte a `url`."""
        if self.mapa is None:
            return None
        return MapaEspecie(
            url=f"/especies/{a_id(self.especie)}/mapa",
            capas=self.mapa.capas,
            puntos=self.mapa.puntos,
            advertencia=self.mapa.advertencia,
        )


class CatalogoCRBioLM:
    """Catálogo respaldado por el servidor MCP de CR-BioLM."""

    def __init__(self) -> None:
        self._mapas: OrderedDict[str, _Mapa] = OrderedDict()
        self._candado = threading.Lock()  # los endpoints corren en varios hilos

    def buscar_especies(self, texto: str) -> list[EspecieCandidata]:
        """Especies que menciona la consulta: 0 = ninguna, 2+ = ambigua (RR_17).

        PROVISIONAL: solo reconoce nombres científicos (dos palabras seguidas que
        sean una especie del catálogo, sin importar mayúsculas). Identificar la
        especie es del módulo de identificación de Jesús (RR_24, 26, 31, 39 y, en
        el sprint 3, nombres comunes RR_25, sinónimos RR_27, ambigüedad RR_28 y
        varias especies RR_36). Cuando esté listo, este método solo lo llama.
        """
        palabras = re.findall(r"[^\W\d_][\w-]*", texto)
        encontradas: dict[str, EspecieCandidata] = {}
        for genero, epiteto in pairwise(palabras):
            manual = self._manual(f"{genero} {epiteto}".capitalize())
            if manual is not None:
                candidata = _candidata(manual.valor)
                encontradas.setdefault(candidata.id, candidata)
        return list(encontradas.values())

    def obtener_especie(self, especie_id: str) -> EspecieCandidata | None:
        manual = self._manual(a_nombre(especie_id))
        return _candidata(manual.valor) if manual else None

    def construir_respuesta(self, especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
        """Respuesta con el texto del Manual y los registros de GBIF (RR_18, RR_41)."""
        datos = self._datos(a_nombre(especie_id))
        if datos is None:
            return None
        ficha = datos.ficha
        return RespuestaConsulta(
            especie=_candidata(ficha),
            texto=ficha.get("distribution_paragraph")
            or "El Manual de Plantas de Costa Rica no describe la distribución de esta especie.",
            elevacion=_elevacion(ficha),
            registros=datos.ocurrencias.registros,
            total_registros=datos.ocurrencias.total,
            fuentes=datos.fuentes(),
            mapa=datos.mapa_especie(),
            avisos=datos.avisos,
        )

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """RR_20. Acepta el id ('quercus-costaricensis') o el nombre científico."""
        datos = self._datos(especie if " " in especie.strip() else a_nombre(especie))
        if datos is None:
            return None
        ficha = datos.ficha
        return FichaEspecie(
            **_candidata(ficha).model_dump(),
            habitat=", ".join(ficha.get("forest_types") or []) or None,
            elevacion=_elevacion(ficha),
            descripcion=ficha.get("morphology") or ficha.get("distribution_paragraph") or None,
            registros=datos.ocurrencias.registros,
            total_registros=datos.ocurrencias.total,
            fuentes=datos.fuentes(),
            mapa=datos.mapa_especie(),
            avisos=datos.avisos,
        )

    def obtener_mapa(self, especie_id: str) -> bytes | None:
        """PNG del mapa (GET /especies/{id}/mapa).

        Sale de la memoria si ya se generó para una respuesta. Si no, se aplican
        las mismas reglas que en la respuesta (RR_60, RR_43, RR_58): sin
        registros suficientes no hay mapa.
        """
        with self._candado:
            if especie_id in self._mapas:
                self._mapas.move_to_end(especie_id)
                return self._mapas[especie_id].png
        datos = self._datos(a_nombre(especie_id))
        return datos.mapa.png if datos and datos.mapa else None

    def _datos(self, nombre: str) -> _Datos | None:
        """Manual, registros de GBIF y mapa de una especie, ya validados.

        None si la especie no está en el catálogo. GBIF y el mapa se piden con
        el nombre de la ficha ya validada (RR_60).
        """
        manual = self._manual(nombre)
        if manual is None:
            return None
        especie = str(manual.valor["species"])
        ocurrencias = _ocurrencias(especie)
        avisos: list[str] = []
        mapa = None
        if ocurrencias.sobre is None:
            avisos.append(_aviso_gbif_no_disponible(ocurrencias.intentos))
        elif not alcanza_para_mapa(ocurrencias.total):
            # RR_43: con datos insuficientes ni siquiera se pide el mapa.
            avisos.append(_aviso_pocos_registros(especie, ocurrencias.total))
        else:
            mapa = self._mapa(a_id(especie), especie)
        return _Datos(manual, ocurrencias, mapa, avisos)

    def _mapa(self, especie_id: str, nombre: str) -> _Mapa | None:
        with self._candado:
            if especie_id in self._mapas:
                self._mapas.move_to_end(especie_id)
                return self._mapas[especie_id]
        mapa = _pedir_mapa(nombre)
        if mapa is not None:
            with self._candado:
                self._mapas[especie_id] = mapa
                while len(self._mapas) > MAPAS_EN_MEMORIA:
                    self._mapas.popitem(last=False)
        return mapa

    @staticmethod
    def _manual(nombre: str) -> Sobre | None:
        """La ficha del Manual, o None si la especie no está en el catálogo.

        RR_60: si la ficha que llega es de otra especie, se descarta como si no
        existiera.
        """
        sobre = mcp_cliente.llamar("get_species", name=nombre)
        if not sobre.valor:
            return None
        recibida = sobre.valor.get("species") if isinstance(sobre.valor, dict) else None
        if not misma_especie(nombre, recibida):
            logger.warning(
                "RR_60: se pidió la ficha de %s y llegó la de %r; se descarta", nombre, recibida
            )
            return None
        return sobre


# --- GBIF: reintentos (RR_58) y validación de los registros (RR_60) -------------


def _ocurrencias(especie: str) -> _Ocurrencias:
    """Los registros de GBIF de la especie, sin los puntos inválidos (RR_60)."""
    sobre, intentos = _consultar_gbif(especie)
    if sobre is None:
        return _Ocurrencias(None, [], 0, intentos)
    valor = sobre.valor if isinstance(sobre.valor, dict) else {}
    puntos = valor.get("points") or []
    validos = [p for p in puntos if punto_valido(p)]
    descartados = len(puntos) - len(validos)
    if descartados:
        logger.warning(
            "RR_60: se descartaron %d de %d registros de GBIF de %s (coordenadas inválidas)",
            descartados,
            len(puntos),
            especie,
        )
    total = max(int(valor.get("n") or 0) - descartados, len(validos))
    return _Ocurrencias(sobre, [_registro(p) for p in validos], total, intentos)


def _consultar_gbif(especie: str) -> tuple[Sobre | None, int]:
    """get_occurrence_points con reintentos (RR_58): (sobre o None, intentos hechos).

    Se reintenta cuando la herramienta falla dentro de CR-BioLM (GBIF caído,
    error de red, respuesta mal formada). No se reintenta si CR-BioLM está
    caído ni si se agotó el tiempo de la consulta (RR_38): esos errores suben.
    """
    intentos = config.GBIF_REINTENTOS + 1
    espera = config.GBIF_ESPERA_REINTENTO_SEGUNDOS
    for intento in range(1, intentos + 1):
        try:
            return mcp_cliente.llamar("get_occurrence_points", species=especie), intento
        except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
            logger.warning(
                "RR_58: GBIF no respondió para %s (intento %d de %d): %s",
                especie,
                intento,
                intentos,
                error,
            )
            if intento == intentos or not alcanza_para_esperar(espera):
                logger.error("RR_58: GBIF no respondió para %s tras %d intentos", especie, intento)
                return None, intento
            time.sleep(espera)
    raise AssertionError("inalcanzable")  # el ciclo siempre retorna


def _aviso_gbif_no_disponible(intentos: int) -> str:
    veces = "1 intento" if intentos == 1 else f"{intentos} intentos"
    return (
        f"No se pudo consultar GBIF ({veces}). La respuesta incluye solo los datos del "
        "Manual, sin registros de presencia ni mapa. Puedes intentarlo de nuevo más tarde."
    )


def _aviso_pocos_registros(especie: str, total: int) -> str:
    """RR_43 criterio 2: por qué no hay mapa."""
    if total == 0:
        return f"GBIF no tiene registros válidos de {especie} en Costa Rica, así que no hay mapa."
    registros = "1 registro válido" if total == 1 else f"{total} registros válidos"
    return (
        f"Solo hay {registros} de {especie} en Costa Rica y se necesitan al menos "
        f"{config.MINIMO_REGISTROS_MAPA} para generar el mapa, así que no se muestra."
    )


# --- conversión de los datos de CR-BioLM a los esquemas del proyecto ------------


def _pedir_mapa(nombre: str) -> _Mapa | None:
    """El mapa de CR-BioLM, o None si no lo genera.

    Si la herramienta falla, la respuesta sale sin mapa en lugar de fallar
    entera. El tiempo agotado sí se deja pasar: es el límite de la consulta (RR_38).
    """
    try:
        sobre = mcp_cliente.llamar("get_species_map_image", species=nombre)
    except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
        logger.warning("CR-BioLM no generó el mapa de %s: %s", nombre, error)
        return None
    valor = sobre.valor or {}
    if not valor.get("png_base64"):
        return None
    capas = [c.strip() for c in str(valor.get("layer_summary", "")).split("|") if c.strip()]
    return _Mapa(
        png=base64.b64decode(valor["png_base64"]),
        capas=capas,
        puntos=int(valor.get("n_pts") or 0),
        advertencia=sobre.advertencia or None,
    )


def _candidata(ficha: dict[str, Any]) -> EspecieCandidata:
    comunes = ficha.get("common_names") or []
    return EspecieCandidata(
        id=a_id(ficha["species"]),
        nombre_comun=comunes[0] if comunes else None,
        nombre_cientifico=ficha["species"],
        familia=ficha.get("family") or SIN_DATO,
    )


def _elevacion(ficha: dict[str, Any]) -> str | None:
    minima, maxima = ficha.get("elev_min"), ficha.get("elev_max")
    if minima is not None and maxima is not None:
        return f"{minima} – {maxima} msnm"
    if minima is not None or maxima is not None:
        return f"{minima if minima is not None else maxima} msnm"
    return None


def _registro(punto: dict[str, Any]) -> RegistroPresencia:
    """Un punto de GBIF ya limpiado por CR-BioLM (RR_42 criterio 3) y validado (RR_60)."""
    return RegistroPresencia(
        localidad=punto.get("region") or SIN_DATO,
        fecha=SIN_DATO,  # CR-BioLM todavía no entrega la fecha del registro
        latitud=punto["lat"],
        longitud=punto["lon"],
        elevacion_m=punto.get("elev_m"),
        fuente=FUENTE_GBIF,
    )


def _fuentes(*sobres: Sobre) -> list[str]:
    """Las citas de cada fuente, sin repetir (trazabilidad, RR_45 y RR_51)."""
    citas = [s.cita or s.fuente for s in sobres]
    return list(dict.fromkeys(c for c in citas if c))
