"""Catálogo de especies con los datos reales de CR-BioLM, por MCP.

Implementa la interfaz `FuenteCatalogo` (services/catalogo.py) con las
herramientas del servidor de CR-BioLM. Todo es L0/L1: no usa el LLM.

    buscar_especies      -> get_species (provisional, ver el método)
    obtener_especie      -> get_species
    construir_respuesta  -> get_species + get_occurrence_points + get_species_map_image
                            + get_relevant_passage (si pregunta algo concreto)
    obtener_ficha        -> get_species + get_occurrence_points + get_species_map_image
    obtener_mapa         -> el mapa en memoria, o lo mismo que la ficha

Todo se combina en un contexto único por especie (services/contexto_especie.py,
RR_45), del que salen la respuesta y la ficha.

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

Según la pregunta (services/intencion.py):

- RR_41: el tipo de pregunta (distribución, descripción...) elige el texto.
  GBIF y el mapa se piden siempre que existan (RR_52, RR_46, RR_59).
- RR_44: si pregunta algo concreto, el texto es el fragmento del Manual que lo
  responde (búsqueda semántica en CR-BioLM); si no, el texto de la ficha.

Se activa con CATALOGO=crbiolm en el .env (ver config.py). Los errores de
conexión con CR-BioLM y el tiempo agotado no se atrapan aquí: los maneja el
servicio de consultas (RR_38) y, más adelante, RR_05. Las excepciones son GBIF
(RR_58, arriba), el mapa y el fragmento (RR_44): si esas herramientas fallan, la
respuesta sale igual, sin mapa o con el texto de la ficha.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
import time
from collections import OrderedDict
from itertools import pairwise
from typing import Any

from .. import config
from ..schemas.consulta import (
    EspecieCandidata,
    FichaEspecie,
    RegistroPresencia,
    RespuestaConsulta,
)
from ..tiempo import alcanza_para_esperar
from . import mcp_cliente
from .contexto_especie import ContextoEspecie, Fragmento, MapaGenerado, Ocurrencias
from .intencion import analizar
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


class CatalogoCRBioLM:
    """Catálogo respaldado por el servidor MCP de CR-BioLM."""

    def __init__(self) -> None:
        self._mapas: OrderedDict[str, MapaGenerado] = OrderedDict()
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
        """Respuesta a la consulta, armada desde el contexto de la especie (RR_45)."""
        contexto = self.contexto(a_nombre(especie_id), texto_consulta)
        if contexto is None:
            return None
        return RespuestaConsulta(
            especie=_candidata(contexto.ficha),
            texto=contexto.texto(),
            elevacion=_elevacion(contexto.ficha),
            registros=contexto.registros,
            total_registros=contexto.total_registros,
            fuentes=contexto.fuentes(),
            mapa=contexto.mapa_especie(_url_del_mapa(contexto.especie)),
            avisos=contexto.avisos,
            geoespacial=contexto.geoespacial,
            procedencia=contexto.procedencia(),
        )

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """RR_20. Acepta el id ('quercus-costaricensis') o el nombre científico.

        La ficha no responde una pregunta: trae todo, incluidos registros y mapa.
        """
        contexto = self.contexto(especie if " " in especie.strip() else a_nombre(especie))
        if contexto is None:
            return None
        ficha = contexto.ficha
        return FichaEspecie(
            **_candidata(ficha).model_dump(),
            habitat=", ".join(ficha.get("forest_types") or []) or None,
            elevacion=_elevacion(ficha),
            descripcion=ficha.get("morphology") or ficha.get("distribution_paragraph") or None,
            registros=contexto.registros,
            total_registros=contexto.total_registros,
            fuentes=contexto.fuentes(),
            mapa=contexto.mapa_especie(_url_del_mapa(contexto.especie)),
            avisos=contexto.avisos,
            procedencia=contexto.procedencia(con_texto=False),
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
        contexto = self.contexto(a_nombre(especie_id))
        return contexto.mapa.png if contexto and contexto.mapa else None

    def contexto(self, nombre: str, pregunta: str = "") -> ContextoEspecie | None:
        """RR_45: toda la información validada de la especie, como un contexto único.

        None si la especie no está en el catálogo. Siempre se piden la ficha, los
        registros de GBIF y el mapa (RR_52, RR_46, RR_59). La pregunta decide:

        - RR_41: su tipo, que elige el texto (contexto_especie.py).
        - RR_44: si pregunta algo concreto, se busca el fragmento del Manual.

        Todo se pide con el nombre de la ficha ya validada (RR_60).
        """
        manual = self._manual(nombre)
        if manual is None:
            return None
        especie = str(manual.valor["species"])
        intencion = analizar(pregunta, especie)
        fragmento = _fragmento(especie, pregunta) if intencion.pregunta_especifica else None

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
        return ContextoEspecie(manual, ocurrencias, mapa, fragmento, avisos, intencion.tipo)

    def _mapa(self, especie_id: str, nombre: str) -> MapaGenerado | None:
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


def _url_del_mapa(especie: str) -> str:
    return f"/especies/{a_id(especie)}/mapa"


# --- Manual vectorizado: el fragmento que responde la pregunta (RR_44) ----------


def _fragmento(especie: str, pregunta: str) -> Fragmento | None:
    """El fragmento del Manual de la especie que mejor responde la pregunta.

    Usa la herramienta get_relevant_passage de CR-BioLM: búsqueda semántica
    (L1, embeddings locales, sin costo) sobre los fragmentos vectorizados del
    Manual de ESA especie. None si no hay fragmento; entonces la respuesta usa
    el texto de la ficha, como antes de RR_44. Pasa cuando:

    - la herramienta no existe todavía o falla (p. ej. la base de vectores de
      CR-BioLM no está levantada),
    - CR-BioLM no tiene texto vectorizado de la especie,
    - el fragmento es de otra especie (RR_60, RR_45 criterio 1).

    El tiempo agotado sí se deja pasar: es el límite de la consulta (RR_38).
    """
    try:
        sobre = mcp_cliente.llamar("get_relevant_passage", species=especie, question=pregunta)
    except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
        logger.warning("RR_44: sin fragmento del Manual para %s: %s", especie, error)
        return None
    valor = sobre.valor if isinstance(sobre.valor, dict) else None
    if not valor:
        logger.info("RR_44: CR-BioLM no dio fragmento de %s: %s", especie, sobre.advertencia)
        return None
    if not misma_especie(especie, valor.get("species")):
        logger.warning(
            "RR_60: se pidió un fragmento de %s y llegó de %r; se descarta",
            especie,
            valor.get("species"),
        )
        return None
    pasajes = valor.get("passages") or []
    mejor = pasajes[0] if pasajes and isinstance(pasajes[0], dict) else {}
    texto = str(mejor.get("text") or "").strip()
    if not texto:
        return None
    return Fragmento(texto=texto, seccion=str(mejor.get("section") or ""))


# --- GBIF: reintentos (RR_58) y validación de los registros (RR_60) -------------


def _ocurrencias(especie: str) -> Ocurrencias:
    """Los registros de GBIF de la especie, sin los puntos inválidos (RR_60)."""
    sobre, intentos = _consultar_gbif(especie)
    if sobre is None:
        return Ocurrencias(None, [], 0, intentos)
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
    return Ocurrencias(sobre, [_registro(p) for p in validos], total, intentos)


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


def _pedir_mapa(nombre: str) -> MapaGenerado | None:
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
    if not _mapa_de_la_especie(nombre, valor):
        return None
    capas = [c.strip() for c in str(valor.get("layer_summary", "")).split("|") if c.strip()]
    return MapaGenerado(
        png=base64.b64decode(valor["png_base64"]),
        capas=capas,
        puntos=int(valor.get("n_pts") or 0),
        advertencia=sobre.advertencia or None,
        cita=sobre.cita,
    )


def _mapa_de_la_especie(nombre: str, valor: dict[str, Any]) -> bool:
    """RR_54 criterios 1 y 2: el mapa que llega es de la especie pedida.

    El mapa se pide con el nombre ya validado (RR_60). Si además CR-BioLM dice
    de qué especie es (`species`) y no coincide, se descarta: es preferible no
    mostrar mapa que mostrar el de otra especie. Los guiones bajos se tratan
    como espacios, porque CR-BioLM los usa en algunos nombres.
    """
    recibida = valor.get("species")
    if recibida is None:
        return True
    if isinstance(recibida, str) and misma_especie(nombre, recibida.replace("_", " ")):
        return True
    logger.warning("RR_54: se pidió el mapa de %s y llegó el de %r; se descarta", nombre, recibida)
    return False


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
