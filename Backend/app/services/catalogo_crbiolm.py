"""Catálogo de especies con los datos reales de CR-BioLM, por MCP.

Implementa la interfaz `FuenteCatalogo` (services/catalogo.py) con las
herramientas del servidor de CR-BioLM. Todo es L0/L1: no usa el LLM.

    buscar_especies      -> get_species (provisional, ver el método)
    obtener_especie      -> get_species
    construir_respuesta  -> get_species + get_occurrence_points + get_species_map_image
    obtener_ficha        -> get_species + get_occurrence_points + get_species_map_image
    obtener_mapa         -> get_species_map_image (con caché en memoria)

Mapas: todos vienen de CR-BioLM (el PNG de render_species_map). Si CR-BioLM no
genera mapa para una especie, la respuesta sale sin mapa; el backend nunca
dibuja uno propio.

Se activa con CATALOGO=crbiolm en el .env (ver config.py). Los errores de MCP
(servidor caído, tiempo agotado) no se atrapan aquí: los maneja el servicio de
consultas (RR_38) y, más adelante, RR_05 y RR_58. La excepción es el mapa: si
la herramienta del mapa falla, la respuesta sale igual, sin mapa.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from ..schemas.consulta import (
    EspecieCandidata,
    FichaEspecie,
    MapaEspecie,
    RegistroPresencia,
    RespuestaConsulta,
)
from . import mcp_cliente
from .mcp_cliente import MCPErrorHerramienta, MCPRespuestaInvalida, Sobre

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
        nombre = a_nombre(especie_id)
        manual = self._manual(nombre)
        if manual is None:
            return None
        gbif = mcp_cliente.llamar("get_occurrence_points", species=nombre)
        ficha = manual.valor
        return RespuestaConsulta(
            especie=_candidata(ficha),
            texto=ficha.get("distribution_paragraph")
            or "El Manual de Plantas de Costa Rica no describe la distribución de esta especie.",
            elevacion=_elevacion(ficha),
            registros=_registros(gbif),
            total_registros=gbif.valor.get("n", 0),
            fuentes=_fuentes(manual, gbif),
            mapa=self._mapa_de(especie_id, nombre),
        )

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """RR_20. Acepta el id ('quercus-costaricensis') o el nombre científico."""
        nombre = especie if " " in especie.strip() else a_nombre(especie)
        manual = self._manual(nombre)
        if manual is None:
            return None
        gbif = mcp_cliente.llamar("get_occurrence_points", species=manual.valor["species"])
        ficha = manual.valor
        registros = _registros(gbif)
        return FichaEspecie(
            **_candidata(ficha).model_dump(),
            habitat=", ".join(ficha.get("forest_types") or []) or None,
            elevacion=_elevacion(ficha),
            descripcion=ficha.get("morphology") or ficha.get("distribution_paragraph") or None,
            registros=registros,
            total_registros=gbif.valor.get("n", 0),
            fuentes=_fuentes(manual, gbif),
            mapa=self._mapa_de(a_id(ficha["species"]), ficha["species"]),
        )

    def obtener_mapa(self, especie_id: str) -> bytes | None:
        """PNG del mapa (GET /especies/{id}/mapa): de la memoria o de CR-BioLM."""
        mapa = self._mapa(especie_id, a_nombre(especie_id))
        return mapa.png if mapa else None

    def _mapa_de(self, especie_id: str, nombre: str) -> MapaEspecie | None:
        """Lo que la respuesta dice del mapa; la imagen se pide aparte a `url`."""
        mapa = self._mapa(especie_id, nombre)
        if mapa is None:
            return None
        return MapaEspecie(
            url=f"/especies/{especie_id}/mapa",
            capas=mapa.capas,
            puntos=mapa.puntos,
            advertencia=mapa.advertencia,
        )

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
        """La ficha del Manual, o None si la especie no está en el catálogo."""
        sobre = mcp_cliente.llamar("get_species", name=nombre)
        return sobre if sobre.valor else None


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


def _registros(gbif: Sobre) -> list[RegistroPresencia]:
    """Puntos de GBIF ya limpiados por CR-BioLM (RR_42 criterio 3)."""
    return [
        RegistroPresencia(
            localidad=p.get("region") or SIN_DATO,
            fecha=SIN_DATO,  # CR-BioLM todavía no entrega la fecha del registro
            latitud=p["lat"],
            longitud=p["lon"],
            elevacion_m=p.get("elev_m"),
            fuente=FUENTE_GBIF,
        )
        for p in (gbif.valor or {}).get("points", [])
    ]


def _fuentes(*sobres: Sobre) -> list[str]:
    """Las citas de cada fuente, sin repetir (trazabilidad, RR_45 y RR_51)."""
    citas = [s.cita or s.fuente for s in sobres]
    return list(dict.fromkeys(c for c in citas if c))
