"""Nombres comunes de especies dentro de la consulta — RR_25.

CR-BioLM asocia un nombre común con sus especies (resolve_common_name, L0) con
las fuentes que tiene: el Manual, iNaturalist, GBIF y Tropicos (criterio 3). La
herramienta recibe UN nombre, no la consulta entera, así que aquí se sacan de la
consulta las frases que podrían ser uno: de 1 a PALABRAS_MAXIMAS palabras
seguidas que no empiecen ni terminen con una palabra de la pregunta ("dónde",
"el", "crece"...). Se prueban de la más larga a la más corta, para que "olla de
mono" gane a "mono".

Variaciones menores (criterio 2):
- tildes y mayúsculas: CR-BioLM compara sin tildes ni mayúsculas ("jicaro" y
  "Jícaro" dan las mismas especies, DEF-15);
- plural: si una frase no está tal cual, se prueba en singular ("ceibas" ->
  "ceiba", `en_singular`). Un nombre que ya termina en "s" ("quiebrapiedras")
  se encuentra en el primer intento.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config
from ..sanitizacion import normalizar
from .intencion import GENERICAS, GEOESPACIALES, VERBOS_DE_LUGAR

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
            # DEF-14: adverbios que rodean un nombre sin ser parte de él
            # ("¿Dónde crece el pochote normalmente?").
            "cerca", "lejos", "mejor", "normalmente", "generalmente", "usualmente",
            "actualmente", "hoy", "aqui", "alli", "tambien", "solo", "mas",
        }
    )
)  # fmt: skip

# DEF-14: palabras que unen las partes de un nombre común ("olla de mono", "flor
# de un día"). Un nombre puede seguir después de "de"/"del" y de un artículo; sin
# "de" delante, un artículo separa ("normalmente el pochote" no es un nombre).
_UNEN_NOMBRE = frozenset({"de", "del"})
_ARTICULOS = frozenset({"el", "la", "los", "las", "un", "una"})


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


def frase_completa(texto: str, frase: Frase) -> Frase:
    """DEF-14: el posible nombre completo que contiene `frase` en `texto`.

    Se extiende `frase` a ambos lados, palabra por palabra y solo entre espacios,
    mientras la vecina sirva para un nombre (no es de la pregunta) o lo una:
    "de"/"del", con un artículo detrás si hace falta ("flor de un día"). Para
    "¿Dónde crece el cedro amargo?" y la frase "amargo" es "cedro amargo"; para
    "¿Dónde crece la olla de mono?" y "olla de mono", la misma frase. Un signo de
    puntuación corta ("el encino, un Quercus") y un artículo sin "de" también
    ("normalmente el pochote").
    """
    palabras = list(_PALABRA.finditer(texto))
    i = next(k for k, p in enumerate(palabras) if p.start() == frase.inicio)
    j = next(k for k, p in enumerate(palabras) if p.end() == frase.fin)

    def seguidas(a: int, b: int) -> bool:
        a, b = min(a, b), max(a, b)
        return not texto[palabras[a].end() : palabras[b].start()].strip()

    def palabra(k: int) -> str:
        return normalizar(palabras[k].group())

    def extender(k: int, paso: int) -> int | None:
        """La palabra hasta donde llega el nombre desde `k` hacia `paso`, o None."""
        v = k + paso
        if not 0 <= v < len(palabras) or not seguidas(k, v):
            return None
        if palabra(v) not in _FUERA_DEL_NOMBRE:
            return v
        unidas: list[str] = []
        while (
            0 <= v < len(palabras)
            and seguidas(v - paso, v)
            and palabra(v) in _UNEN_NOMBRE | _ARTICULOS
        ):
            unidas.append(palabra(v))
            v += paso
        if not unidas or len(unidas) > 2 or not 0 <= v < len(palabras):
            return None
        if not seguidas(v - paso, v) or palabra(v) in _FUERA_DEL_NOMBRE:
            return None
        # "olla de mono de Guanacaste": después de "de", un lugar es la zona (RR_39).
        if palabra(v) in GEOESPACIALES:
            return None
        # En el texto, la unión empieza con "de": "olla de mono", "flor de un día".
        primera = unidas[0] if paso > 0 else unidas[-1]
        return v if primera in _UNEN_NOMBRE else None

    while (k := extender(i, -1)) is not None:
        i = k
    while (k := extender(j, 1)) is not None:
        j = k
    inicio, fin = palabras[i].start(), palabras[j].end()
    return Frase(texto[inicio:fin], inicio, fin)


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
