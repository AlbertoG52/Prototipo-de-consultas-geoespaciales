"""Contexto único de una especie — RR_45 (combinación de fuentes).

`ContextoEspecie` junta, ya validado, todo lo que CR-BioLM sabe de una especie:

    fuente estructurada   la ficha del Manual (familia, elevación, regiones...)
    fuente vectorizada    el fragmento del Manual que responde la pregunta (RR_44)
    GBIF                  los registros de presencia (RR_42, RR_43, RR_58, RR_60)
    mapa                  el PNG que genera CR-BioLM (RR_41)
    redacción del LLM     la respuesta en lenguaje natural de answer_question (RR_49)

Criterios de RR_45:
1. Las fuentes corresponden a la misma especie: services/catalogo_crbiolm.py
   descarta, antes de armar el contexto, todo lo que no sea de la especie pedida
   (RR_60), incluido el fragmento vectorizado.
2. Se entrega como un contexto único: este objeto. De él salen la respuesta del
   chat y la ficha. La respuesta del chat puede llevar además el texto que
   redacta el LLM de CR-BioLM (RR_49, `redaccion`).
3. Trazabilidad: `procedencia()` dice de dónde sale cada dato de la respuesta.

No llama a CR-BioLM: solo combina lo que ya se pidió.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..dominio import DatoRespuesta
from ..schemas.consulta import MapaEspecie, Procedencia, RegistroPresencia
from .intencion import TipoPregunta
from .mcp_cliente import Sobre

MANUAL = "Manual de Plantas de Costa Rica"
GBIF = "GBIF"
CR_BIOLM = "CR-BioLM"

SIN_TEXTO = "El Manual de Plantas de Costa Rica no describe la distribución de esta especie."

# RR_49: de dónde sale el texto cuando lo redacta el LLM de CR-BioLM.
REDACTADO_CON_IA = "respuesta redactada con IA a partir del Manual"

# "Manual de Plantas de Costa Rica, Tomo V, p. 779 (Quercus costaricensis)":
# CR-BioLM termina cada cita del LLM con la especie entre paréntesis.
_ESPECIE_AL_FINAL = re.compile(r"\s*\(([^()]+)\)\s*$")

# Secciones del Manual en los fragmentos de CR-BioLM (pg_store.chunk_texts).
SECCIONES = {
    "distribution": "distribución",
    "description": "descripción",
}

# RR_45: cómo se describe el origen de cada dato. Son textos para el usuario: las
# citas técnicas de CR-BioLM (filtros de GBIF, archivos del mapa) no se muestran.
FICHA = "ficha de la especie"
DE_LA_PREGUNTA = "fragmento más relacionado con la pregunta"  # RR_44
DETALLE_REGISTROS = "registros de presencia en Costa Rica, consultados en vivo"
DETALLE_MAPA = (
    "elaborado con el Manual, los registros de GBIF, un modelo de elevación "
    "y las regiones botánicas"
)


@dataclass(frozen=True)
class MapaGenerado:
    """El mapa de CR-BioLM (get_species_map_image)."""

    png: bytes
    capas: list[str]
    puntos: int
    advertencia: str | None


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
class RedaccionIA:
    """RR_49: la respuesta que redacta el LLM de CR-BioLM (answer_question), ya validada.

    `texto` trae las citas del Manual dentro, p. ej. "【Quercus costaricensis
    (Tomo V, p.779)】"; `citas` son las mismas referencias, completas.
    """

    texto: str
    citas: list[str]


@dataclass(frozen=True)
class ContextoEspecie:
    """Toda la información validada de una especie, combinada (ver el módulo)."""

    manual: Sobre  # ficha estructurada del Manual (get_species)
    ocurrencias: Ocurrencias
    mapa: MapaGenerado | None
    fragmento: Fragmento | None  # None: no hubo pregunta concreta o no se encontró
    avisos: list[str]
    tipo: TipoPregunta = TipoPregunta.GENERAL  # RR_41: qué pregunta la consulta
    # RR_49: solo en la respuesta del chat, y solo si el LLM respondió bien.
    redaccion: RedaccionIA | None = None

    @property
    def ficha(self) -> dict[str, Any]:
        return self.manual.valor

    @property
    def especie(self) -> str:
        return str(self.ficha["species"])

    @property
    def geoespacial(self) -> bool:
        """RR_41: la pregunta pide información geográfica (no cambia lo que se pide)."""
        return self.tipo is not TipoPregunta.DESCRIPCION

    @property
    def registros(self) -> list[RegistroPresencia]:
        return self.ocurrencias.registros

    @property
    def total_registros(self) -> int:
        return self.ocurrencias.total

    @property
    def gbif(self) -> Sobre | None:
        """El sobre de GBIF, o None si GBIF no respondió (RR_58)."""
        return self.ocurrencias.sobre

    def texto(self) -> str:
        """El texto de la respuesta del chat."""
        return self._texto()[0]

    def fuentes(self) -> list[str]:
        """Las fuentes consultadas, sin repetir (RR_51): la cita del Manual y "GBIF"."""
        citas = [self.manual.cita or MANUAL]
        if self.gbif is not None:
            citas.append(GBIF)
        if self.redaccion is not None:
            # RR_50: las páginas del Manual que citó el LLM también son fuentes.
            citas.extend(sin_especie(c) for c in self.redaccion.citas)
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
        ficha = ubicacion or FICHA
        origen = [Procedencia(dato=DatoRespuesta.ESPECIE, fuente=MANUAL, detalle=ficha)]
        if con_texto:
            detalle = self._texto()[1]
            if ubicacion:
                detalle = f"{ubicacion} · {detalle}"
            origen.append(Procedencia(dato=DatoRespuesta.TEXTO, fuente=MANUAL, detalle=detalle))
        if self.ficha.get("elev_min") is not None or self.ficha.get("elev_max") is not None:
            origen.append(Procedencia(dato=DatoRespuesta.ELEVACION, fuente=MANUAL, detalle=ficha))
        if self.gbif is not None:
            origen.append(
                Procedencia(dato=DatoRespuesta.REGISTROS, fuente=GBIF, detalle=DETALLE_REGISTROS)
            )
        if self.mapa is not None:
            origen.append(
                Procedencia(dato=DatoRespuesta.MAPA, fuente=CR_BIOLM, detalle=DETALLE_MAPA)
            )
        return origen

    def _texto(self) -> tuple[str, str]:
        """(texto, de dónde sale). Orden de preferencia:

        1. La respuesta redactada por el LLM de CR-BioLM (RR_49).
        2. El fragmento que responde la pregunta (RR_44).
        3. Según el tipo de pregunta (RR_41): la morfología si pregunta cómo es la
           planta. RR_29 (Cristopher): aquí va el texto de hábitat para HABITAT.
        4. El párrafo de distribución.
        """
        if self.redaccion is not None:
            return self.redaccion.texto, REDACTADO_CON_IA
        if self.fragmento is not None:
            seccion = SECCIONES.get(self.fragmento.seccion, self.fragmento.seccion)
            return self.fragmento.texto, f"{seccion} · {DE_LA_PREGUNTA}"
        if self.tipo is TipoPregunta.DESCRIPCION and self.ficha.get("morphology"):
            return str(self.ficha["morphology"]), SECCIONES["description"]
        if self.ficha.get("distribution_paragraph"):
            return str(self.ficha["distribution_paragraph"]), SECCIONES["distribution"]
        return SIN_TEXTO, "sin texto en el Manual"


def _ubicacion_en_el_manual(cita: str) -> str:
    """'Manual de Plantas de Costa Rica, Tomo V, p. 779' -> 'Tomo V, p. 779'."""
    prefijo = f"{MANUAL}, "
    return cita[len(prefijo) :] if cita.startswith(prefijo) else cita


def especie_de_la_cita(cita: str) -> str | None:
    """'..., Tomo V, p. 779 (Quercus costaricensis)' -> 'Quercus costaricensis'."""
    encontrada = _ESPECIE_AL_FINAL.search(cita)
    return encontrada.group(1).strip() if encontrada else None


def sin_especie(cita: str) -> str:
    """'..., Tomo V, p. 779 (Quercus costaricensis)' -> '..., Tomo V, p. 779'."""
    return _ESPECIE_AL_FINAL.sub("", cita).strip()
