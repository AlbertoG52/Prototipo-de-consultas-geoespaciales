"""Corrección de errores ortográficos en nombres científicos.

Un par de palabras que no es un nombre del catálogo se cambia por el nombre que está a lo
sumo a LETRAS_MAXIMAS_CORRECCION letras de diferencia: "Querus costaricencis" está a dos de
"Quercus costaricensis". Solo se corrige si hay un único nombre así de cercano. Se compara
sin tildes ni mayúsculas y solo cambia el nombre mal escrito. El texto corregido se usa
para buscar; se guarda y muestra el que escribió el usuario.
"""

from __future__ import annotations

import difflib
import re
from itertools import pairwise

from .. import config
from ..sanitizacion import normalizar

_PALABRA = re.compile(r"[^\W\d_][\w-]*")

# difflib descarta rápido los nombres muy distintos antes de contar letras. Con 0.7 no se
# pierde ningún nombre a dos letras de distancia.
_PARECIDO_MINIMO = 0.7
_CANDIDATOS = 5


def corregir_nombres(texto: str, nombres: dict[str, str]) -> str:
    """`texto` con cada nombre científico mal escrito cambiado por el del catálogo.

    `nombres`: nombre normalizado -> nombre como lo guarda el catálogo.
    """
    palabras = list(_PALABRA.finditer(texto))
    cambios: list[tuple[int, int, str]] = []
    for genero, epiteto in pairwise(palabras):
        par = normalizar(f"{genero.group()} {epiteto.group()}")
        if par in nombres or (cambios and genero.start() < cambios[-1][1]):
            continue
        cercano = _unico_cercano(par, nombres)
        if cercano is not None:
            cambios.append((genero.start(), epiteto.end(), nombres[cercano]))
    for inicio, fin, nombre in reversed(cambios):
        texto = texto[:inicio] + nombre + texto[fin:]
    return texto


def _unico_cercano(par: str, nombres: dict[str, str]) -> str | None:
    """El nombre a lo sumo a LETRAS_MAXIMAS_CORRECCION letras de `par`, si es uno solo."""
    candidatos = difflib.get_close_matches(par, nombres, n=_CANDIDATOS, cutoff=_PARECIDO_MINIMO)
    distancias = sorted(
        (d, nombre)
        for nombre in candidatos
        if (d := letras_distintas(par, nombre)) <= config.LETRAS_MAXIMAS_CORRECCION
    )
    if not distancias or (len(distancias) > 1 and distancias[1][0] == distancias[0][0]):
        return None
    return distancias[0][1]


def letras_distintas(a: str, b: str) -> int:
    """Letras cambiadas, faltantes o sobrantes entre `a` y `b` (distancia de Levenshtein)."""
    anterior = list(range(len(b) + 1))
    for i, letra_a in enumerate(a, 1):
        actual = [i]
        for j, letra_b in enumerate(b, 1):
            actual.append(
                min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (letra_a != letra_b))
            )
        anterior = actual
    return anterior[-1]
