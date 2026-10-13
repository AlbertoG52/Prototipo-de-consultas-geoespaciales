"""Región o zona mencionada en la consulta — RR_39.

Reconoce las regiones botánicas y las vertientes del Manual (get_vocabulary de
CR-BioLM): son los mismos nombres que trae cada punto de GBIF en `region` y
`vertiente`. Las provincias no son regiones botánicas y no se reconocen.

En orden:
1. El nombre completo de una región ("Cordillera de Talamanca", "Golfito"),
   con sus variantes que empiezan igual ("Valle Central" incluye la Occidental
   y la Oriental).
2. Si no hay ninguno, una palabra propia de una o varias regiones
   ("Talamanca": la Cordillera y Baja Talamanca). Las genéricas ("cordillera",
   "valle", "central", "general"...) no cuentan solas.
3. La vertiente: "Caribe" o "Pacífico".

Sin región ni vertiente devuelve None y la búsqueda sigue sin filtro
(criterio 3). Se compara sin tildes, mayúsculas ni signos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..sanitizacion import normalizar

# Palabras de los nombres de región que, solas, no identifican una región.
_GENERICAS = frozenset(
    {
        "baja", "central", "clara", "colorado", "cordillera", "de", "del", "fila", "filas",
        "general", "llanura", "llanuras", "los", "norte", "occidental", "oriental",
        "peninsula", "san", "santa", "sur", "valle", "y",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Zona:
    regiones: frozenset[str]  # regiones, en forma de `_clave`; vacío = cualquiera
    vertiente: str | None  # "caribe" o "pacifico"

    def incluye(self, punto: dict[str, Any]) -> bool:
        """True si el punto de GBIF está en la zona, según sus campos region y vertiente."""
        if self.regiones and _clave(punto.get("region") or "") not in self.regiones:
            return False
        return self.vertiente is None or self.vertiente in _clave(punto.get("vertiente") or "")


def extraer_zona(texto: str, vocabulario: dict[str, Any] | None) -> Zona | None:
    """La zona que menciona `texto`, o None si no menciona ninguna (ver el módulo)."""
    if not vocabulario:
        return None
    frase = f" {_clave(texto)} "
    regiones = vocabulario.get("regions") or []
    elegidas = _por_nombre(frase, regiones) or _por_palabra(frase, regiones)
    vertientes = (_clave(v) for v in vocabulario.get("vertientes") or [])
    vertiente = next((v for v in vertientes if f" {v} " in frase), None)
    if not elegidas and vertiente is None:
        return None
    return Zona(frozenset(elegidas), vertiente)


def _por_nombre(frase: str, regiones: list[str]) -> set[str]:
    """Regiones cuyo nombre, o una de sus partes ("Osa - Golfito"), aparece completo."""
    mencionadas = {p for r in regiones for p in _partes(r) if f" {p} " in frase}
    return {
        _clave(r)
        for r in regiones
        if any(p == m or p.startswith(f"{m} ") for p in _partes(r) for m in mencionadas)
    }


def _por_palabra(frase: str, regiones: list[str]) -> set[str]:
    """Regiones que comparten con la frase una palabra propia (no genérica)."""
    palabras = set(frase.split()) - _GENERICAS
    return {_clave(r) for r in regiones if palabras & set(_clave(r).split())}


def _partes(region: str) -> list[str]:
    """'Península de Osa - Golfito' -> ['peninsula de osa', 'golfito']."""
    return [c for parte in re.split(r"[/-]", region) if (c := _clave(parte))]


def _clave(texto: str) -> str:
    """'Fila Costeña (Norte)' -> 'fila costena norte': para comparar nombres."""
    return " ".join(re.findall(r"[a-z0-9]+", normalizar(texto)))
