"""Contexto único de una especie — RR_45 (combinación de fuentes).

`ContextoEspecie` junta, ya validado, todo lo que CR-BioLM sabe de una especie:

    fuente estructurada   la ficha del Manual (familia, elevación, regiones...)
    fuente vectorizada    el fragmento del Manual que responde la pregunta (RR_44)
    GBIF                  los registros de presencia (RR_42, RR_43, RR_58, RR_60)
    mapa                  el PNG que genera CR-BioLM (RR_41)

Criterios de RR_45:
1. Las fuentes corresponden a la misma especie: services/catalogo_crbiolm.py
   descarta, antes de armar el contexto, todo lo que no sea de la especie pedida
   (RR_60), incluido el fragmento vectorizado.
2. Se entrega como un contexto único: este objeto. De él salen la respuesta del
   chat y la ficha, y es lo que recibirá el módulo de respuesta con LLM (L2)
   cuando se integre.
3. Trazabilidad: `procedencia()` dice de dónde sale cada dato de la respuesta.

No llama a CR-BioLM: solo combina lo que ya se pidió.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..dominio import DatoRespuesta
from ..schemas.consulta import MapaEspecie, Procedencia, RegistroPresencia
from .mcp_cliente import Sobre

MANUAL = "Manual de Plantas de Costa Rica"
GBIF = "GBIF"
CR_BIOLM = "CR-BioLM"

SIN_TEXTO = "El Manual de Plantas de Costa Rica no describe la distribución de esta especie."

# Secciones del Manual en los fragmentos de CR-BioLM (pg_store.chunk_texts).
SECCIONES = {
    "distribution": "párrafo de distribución",
    "description": "descripción (morfología y discusión)",
}


@dataclass(frozen=True)
class MapaGenerado:
    """El mapa de CR-BioLM (get_species_map_image)."""

    png: bytes
    capas: list[str]
    puntos: int
    advertencia: str | None
    cita: str = ""


@dataclass(frozen=True)
class Ocurrencias:
    """Los registros de GBIF de una especie, ya validados (RR_60)."""

    sobre: Sobre | None  # None: GBIF no respondió en ningún intento (RR_58)
    registros: list[RegistroPresencia]
    # Registros válidos en total. Puede ser mayor que len(registros): CR-BioLM
    # cuenta todos pero entrega como máximo 500 puntos.
    total: int
    intentos: int


@dataclass(frozen=True)
class Fragmento:
    """RR_44: el fragmento del Manual que mejor responde la pregunta."""

    texto: str
    seccion: str  # "distribution" o "description"


@dataclass(frozen=True)
class ContextoEspecie:
    """Toda la información validada de una especie, combinada (ver el módulo)."""

    manual: Sobre  # ficha estructurada del Manual (get_species)
    # None cuando la consulta no es geoespacial (RR_41): no se pidió GBIF.
    ocurrencias: Ocurrencias | None
    mapa: MapaGenerado | None
    fragmento: Fragmento | None  # None: no hubo pregunta concreta o no se encontró
    avisos: list[str]

    @property
    def ficha(self) -> dict[str, Any]:
        return self.manual.valor

    @property
    def especie(self) -> str:
        return str(self.ficha["species"])

    @property
    def geoespacial(self) -> bool:
        return self.ocurrencias is not None

    @property
    def registros(self) -> list[RegistroPresencia]:
        return self.ocurrencias.registros if self.ocurrencias else []

    @property
    def total_registros(self) -> int:
        return self.ocurrencias.total if self.ocurrencias else 0

    @property
    def gbif(self) -> Sobre | None:
        """El sobre de GBIF, o None si no se consultó o no respondió."""
        return self.ocurrencias.sobre if self.ocurrencias else None

    def texto(self) -> str:
        """El texto de la respuesta del chat."""
        return self._texto()[0]

    def fuentes(self) -> list[str]:
        """Las citas de cada fuente, sin repetir (RR_51)."""
        citas = [s.cita or s.fuente for s in (self.manual, self.gbif) if s is not None]
        return list(dict.fromkeys(c for c in citas if c))

    def mapa_especie(self, url: str) -> MapaEspecie | None:
        """Lo que la respuesta dice del mapa; la imagen se pide aparte a `url`."""
        if self.mapa is None:
            return None
        return MapaEspecie(
            url=url,
            capas=self.mapa.capas,
            puntos=self.mapa.puntos,
            advertencia=self.mapa.advertencia,
        )

    def procedencia(self, *, con_texto: bool = True) -> list[Procedencia]:
        """RR_45 criterio 3: el origen de cada dato que trae la respuesta.

        `con_texto=False` para la ficha, que no muestra el texto del chat.
        """
        ubicacion = _ubicacion_en_el_manual(self.manual.cita)
        ficha = f"{ubicacion} · ficha estructurada" if ubicacion else "ficha estructurada"
        origen = [Procedencia(dato=DatoRespuesta.ESPECIE, fuente=MANUAL, detalle=ficha)]
        if con_texto:
            detalle = self._texto()[1]
            if ubicacion:
                detalle = f"{ubicacion} · {detalle}"
            origen.append(Procedencia(dato=DatoRespuesta.TEXTO, fuente=MANUAL, detalle=detalle))
        if self.ficha.get("elev_min") is not None or self.ficha.get("elev_max") is not None:
            origen.append(Procedencia(dato=DatoRespuesta.ELEVACION, fuente=MANUAL, detalle=ficha))
        if self.gbif is not None:
            detalle = "consulta en vivo, solo registros válidos en Costa Rica"
            if self.gbif.cita:
                detalle = f"{self.gbif.cita} · {detalle}"
            origen.append(Procedencia(dato=DatoRespuesta.REGISTROS, fuente=GBIF, detalle=detalle))
        if self.mapa is not None:
            origen.append(
                Procedencia(
                    dato=DatoRespuesta.MAPA,
                    fuente=CR_BIOLM,
                    detalle=self.mapa.cita or "mapa de distribución",
                )
            )
        return origen

    def _texto(self) -> tuple[str, str]:
        """(texto, de dónde sale). Orden de preferencia:

        1. El fragmento que responde la pregunta (RR_44).
        2. Si la pregunta no es geoespacial, la morfología: describe la planta.
        3. El párrafo de distribución.
        """
        if self.fragmento is not None:
            seccion = SECCIONES.get(self.fragmento.seccion, self.fragmento.seccion)
            return self.fragmento.texto, f"{seccion} · búsqueda semántica"
        if not self.geoespacial and self.ficha.get("morphology"):
            return str(self.ficha["morphology"]), SECCIONES["description"]
        if self.ficha.get("distribution_paragraph"):
            return str(self.ficha["distribution_paragraph"]), SECCIONES["distribution"]
        return SIN_TEXTO, "sin texto en el Manual"


def _ubicacion_en_el_manual(cita: str) -> str:
    """'Manual de Plantas de Costa Rica, Tomo V, p. 779' -> 'Tomo V, p. 779'."""
    prefijo = f"{MANUAL}, "
    return cita[len(prefijo) :] if cita.startswith(prefijo) else cita
