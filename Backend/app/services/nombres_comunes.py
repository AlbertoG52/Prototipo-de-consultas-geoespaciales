"""Nombres comunes de especies dentro de la consulta — RR_25.

CR-BioLM asocia un nombre común con sus especies (resolve_common_name, L0) con
las fuentes que tiene: el Manual, iNaturalist, GBIF y Tropicos (criterio 3). La
herramienta recibe UN nombre, no la consulta entera, así que aquí se sacan de la
consulta las frases que podrían ser uno: de 1 a PALABRAS_MAXIMAS palabras
seguidas que no empiecen ni terminen con una palabra de la pregunta ("dónde",
"el", "crece"...). Se prueban de la más larga a la más corta, para que "olla de
mono" gane a "mono".

Variaciones menores (criterio 2):
- tildes y mayúsculas: CR-BioLM compara primero con tildes ("poró") y, si no
  encuentra, sin ellas;
- plural: si una frase no está tal cual, se prueba en singular ("ceibas" ->
  "ceiba", `en_singular`). Un nombre que ya termina en "s" ("quiebrapiedras")
  se encuentra en el primer intento.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config
from ..sanitizacion import normalizar
from .intencion import GENERICAS, VERBOS_DE_LUGAR

PALABRAS_MAXIMAS = 4  # "flor de un día"

_PALABRA = re.compile(r"[^\W\d_][\w-]*")

# Palabras de la pregunta, no del nombre: una frase no empieza ni termina con
# ellas. No están los lugares ni las partes de la planta, que sí aparecen en
# nombres comunes ("guanacaste", "flor de mayo").
_FUERA_DEL_NOMBRE = (
    GENERICAS
    | VERBOS_DE_LUGAR
    | frozenset(
        {
            "donde", "cuando", "cuanto", "cuanta", "cuantos", "cuantas", "quien",
            "quienes", "crecer", "vive", "viven", "habita", "habitan", "distribucion",
            "mapa", "registros", "ubicacion", "zona", "region", "altitud", "elevacion",
            "habitat", "costa", "rica",
        }
    )
)  # fmt: skip


@dataclass(frozen=True)
class Frase:
    """Palabras seguidas de la consulta, como las escribió el usuario."""

    texto: str
    inicio: int  # posición del primer carácter en la consulta
    fin: int  # posición siguiente al último

    def se_cruza_con(self, otra: Frase) -> bool:
        return self.inicio < otra.fin and otra.inicio < self.fin


def frases_candidatas(texto: str) -> list[Frase]:
    """Las frases de `texto` que podrían ser un nombre común, de la más larga a la más corta.

    A lo sumo config.NOMBRES_COMUNES_FRASES_MAXIMAS, porque cada una es una
    consulta a CR-BioLM.
    """
    palabras = list(_PALABRA.finditer(texto))
    sirven = [normalizar(p.group()) not in _FUERA_DEL_NOMBRE for p in palabras]
    frases: list[Frase] = []
    for largo in range(min(PALABRAS_MAXIMAS, len(palabras)), 0, -1):
        for i in range(len(palabras) - largo + 1):
            if sirven[i] and sirven[i + largo - 1]:
                inicio, fin = palabras[i].start(), palabras[i + largo - 1].end()
                frases.append(Frase(texto[inicio:fin], inicio, fin))
    return frases[: config.NOMBRES_COMUNES_FRASES_MAXIMAS]


def en_singular(nombre: str) -> str | None:
    """'ollas de monos' -> 'olla de mono'; None si ninguna palabra está en plural.

    Las palabras cortas ("las") y las de la pregunta ("datos") no se tocan.
    """
    palabras = nombre.split()
    singular = [
        p[:-1] if len(p) > 3 and p.lower().endswith("s") and normalizar(p) not in GENERICAS else p
        for p in palabras
    ]
    return " ".join(singular) if singular != palabras else None
