"""Contexto único de una especie.

`ContextoEspecie` junta, ya validado, lo que CR-BioLM sabe de una especie:

  fuente estructurada   la ficha del Manual (familia, elevación, regiones...)
  fuente vectorizada    el fragmento del Manual que responde la pregunta
  GBIF                  los registros de presencia
  mapa                  el PNG que genera CR-BioLM
  redacción del LLM     la respuesta en lenguaje natural de answer_question

Todo corresponde a la misma especie (services/catalogo_crbiolm.py descarta lo demás). De
este objeto salen la respuesta del chat y la ficha, y `procedencia()` dice de dónde sale
cada dato. No llama a CR-BioLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..dominio import DatoRespuesta, TipoPregunta
from ..schemas.consulta import MapaEspecie, Procedencia, RegistroPresencia
from ..tiempo import fecha_para_mostrar
from .habitat import texto_de_habitat
from .mcp_cliente import Sobre

MANUAL = "Manual de Plantas de Costa Rica"
GBIF = "GBIF"
CR_BIOLM = "CR-BioLM"

SIN_TEXTO = "El Manual de Plantas de Costa Rica no describe la distribución de esta especie."
# Pregunta cómo es la planta y la ficha no trae su descripción.
SIN_DESCRIPCION = "El Manual de Plantas de Costa Rica no trae la descripción de esta especie."
DE_LA_DISTRIBUCION = "se muestra lo que dice de su distribución"

# Origen del texto cuando lo redacta el LLM de CR-BioLM.
REDACTADO_CON_IA = "respuesta redactada con IA a partir del Manual"

# "Manual de Plantas de Costa Rica, Tomo V, p. 779 (Quercus costaricensis)":
# CR-BioLM termina cada cita del LLM con la especie entre paréntesis.
_ESPECIE_AL_FINAL = re.compile(r"\s*\(([^()]+)\)\s*$")

# Secciones del Manual en los fragmentos de CR-BioLM (pg_store.chunk_texts).
SECCIONES = {
    "distribution": "distribución",
    "description": "descripción",
}

# Cómo se describe el origen de cada dato. Son textos para el usuario: las citas técnicas de
# CR-BioLM no se muestran.
FICHA = "ficha de la especie"
DE_LA_PREGUNTA = "fragmento más relacionado con la pregunta"
DETALLE_HABITAT = "hábitat: forma de crecimiento, tipo de bosque, vertiente y elevación"
# CR-BioLM guarda los registros de GBIF y los actualiza cada cierto tiempo; el detalle dice
# de cuándo son.
DETALLE_REGISTROS = "registros de presencia en Costa Rica"
# Las mismas fuentes que acredita el pie del mapa de CR-BioLM (render_species_map). Si
# cambian las capas del mapa, se actualiza este texto.
DETALLE_MAPA = (
    "elaborado con las regiones botánicas de M. V. Castro (Manual de Plantas de "
    "Costa Rica), las áreas silvestres protegidas del SINAC, la altitud de SRTM e "
    "INEC y los registros de GBIF"
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
    """Registros de GBIF de una especie, ya validados."""

    sobre: Sobre | None  # None: GBIF no respondió en ningún intento
    registros: list[RegistroPresencia]
    # Registros válidos en total. Puede ser mayor que len(registros): CR-BioLM
    # cuenta todos pero entrega como máximo 500 puntos.
    total: int
    intentos: int
    # Cuándo descargó CR-BioLM estos registros (None si no lo indica) y si son los
    # anteriores porque no pudo actualizarlos.
    actualizado_en: datetime | None = None
    desactualizado: bool = False


@dataclass(frozen=True)
class Fragmento:
    """Fragmento del Manual que mejor responde la pregunta."""

    texto: str
    seccion: str  # "distribution" o "description"


@dataclass(frozen=True)
class RedaccionIA:
    """Respuesta que redacta el LLM de CR-BioLM (answer_question), ya validada.

    `texto` trae las citas del Manual, p. ej. "【Quercus costaricensis (Tomo V, p.779)】";
    `citas` son las mismas referencias completas.
    """

    texto: str
    citas: list[str]


@dataclass(frozen=True)
class ContextoEspecie:
    """Información validada de una especie, combinada."""

    manual: Sobre  # ficha estructurada del Manual (get_species)
    ocurrencias: Ocurrencias
    mapa: MapaGenerado | None
    fragmento: Fragmento | None  # None: no hubo pregunta concreta o no se encontró
    avisos: list[str]
    tipo: TipoPregunta = TipoPregunta.GENERAL  # qué pregunta la consulta
    # Solo en la respuesta del chat, y solo si el LLM respondió bien.
    redaccion: RedaccionIA | None = None

    @property
    def ficha(self) -> dict[str, Any]:
        return self.manual.valor

    @property
    def especie(self) -> str:
        return str(self.ficha["species"])

    @property
    def geoespacial(self) -> bool:
        """La pregunta pide información geográfica."""
        return self.tipo is not TipoPregunta.DESCRIPCION

    @property
    def registros(self) -> list[RegistroPresencia]:
        return self.ocurrencias.registros

    @property
    def total_registros(self) -> int:
        return self.ocurrencias.total

    @property
    def gbif(self) -> Sobre | None:
        """El sobre de GBIF, o None si GBIF no respondió."""
        return self.ocurrencias.sobre

    @property
    def registros_actualizados_en(self) -> datetime | None:
        """Cuándo se descargaron de GBIF los registros; None sin registros."""
        return self.ocurrencias.actualizado_en if self.gbif is not None else None

    def texto(self) -> str:
        """El texto de la respuesta del chat."""
        return self._texto()[0]

    @property
    def gbif_aporto_registros(self) -> bool:
        """GBIF respondió y trajo al menos un registro válido."""
        return self.gbif is not None and self.total_registros > 0

    def fuentes(self) -> list[str]:
        """Fuentes usadas, sin repetir: la cita del Manual y "GBIF" (solo si aportó
        registros).
        """
        citas = [self.manual.cita or MANUAL]
        if self.gbif_aporto_registros:
            citas.append(GBIF)
        if self.redaccion is not None:
            # Las páginas del Manual que citó el LLM también son fuentes.
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
        """Origen de cada dato de la respuesta. `con_texto=False` para la ficha, que no
        muestra el texto del chat.
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
        if self.gbif_aporto_registros:
            detalle = _detalle_registros(self.registros_actualizados_en)
            origen.append(Procedencia(dato=DatoRespuesta.REGISTROS, fuente=GBIF, detalle=detalle))
        if self.mapa is not None:
            origen.append(
                Procedencia(dato=DatoRespuesta.MAPA, fuente=CR_BIOLM, detalle=DETALLE_MAPA)
            )
        return origen

    def avisos_del_texto(self) -> list[str]:
        """Si pregunta cómo es la planta y el Manual no la describe, lo indica, para que el
        texto no parezca una descripción.
        """
        if self.tipo is not TipoPregunta.DESCRIPCION or self.ficha.get("morphology"):
            return []
        # El fragmento del Manual puede traer la descripción aunque la ficha no la tenga.
        if self.fragmento is not None and self.fragmento.seccion == "description":
            return []
        if SECCIONES["distribution"] in self._texto()[1]:
            return [f"{SIN_DESCRIPCION.removesuffix('.')}; {DE_LA_DISTRIBUCION}."]
        return [SIN_DESCRIPCION]

    def _texto(self) -> tuple[str, str]:
        """(texto, origen). Orden de preferencia:

        1. La respuesta redactada por el LLM de CR-BioLM.
        2. El fragmento del Manual que responde la pregunta.
        3. Según el tipo de pregunta: el hábitat de la ficha (services/habitat.py) o la
           morfología.
        4. El párrafo de distribución.
        """
        if self.redaccion is not None:
            return self.redaccion.texto, REDACTADO_CON_IA
        if self.fragmento is not None:
            seccion = SECCIONES.get(self.fragmento.seccion, self.fragmento.seccion)
            return self.fragmento.texto, f"{seccion} · {DE_LA_PREGUNTA}"
        if self.tipo is TipoPregunta.HABITAT and (habitat := texto_de_habitat(self.ficha)):
            return habitat, DETALLE_HABITAT
        if self.tipo is TipoPregunta.DESCRIPCION and self.ficha.get("morphology"):
            return str(self.ficha["morphology"]), SECCIONES["description"]
        if self.ficha.get("distribution_paragraph"):
            return str(self.ficha["distribution_paragraph"]), SECCIONES["distribution"]
        return SIN_TEXTO, "sin texto en el Manual"


def _detalle_registros(actualizado_en: datetime | None) -> str:
    """'registros de presencia en Costa Rica, actualizados el 19/10/2026'."""
    if actualizado_en is None:
        return DETALLE_REGISTROS
    return f"{DETALLE_REGISTROS}, actualizados el {fecha_para_mostrar(actualizado_en)}"


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
