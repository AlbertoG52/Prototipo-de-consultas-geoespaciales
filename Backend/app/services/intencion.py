"""Qué pide la consulta — RR_41 criterio 1. PROVISIONAL.

Decide, a partir del texto, si la consulta requiere información geoespacial
(registros de GBIF y mapa) y si pregunta algo concreto además del nombre de la
especie (para RR_44, el fragmento del Manual que lo responde).

Es un clasificador por palabras clave, a propósito simple: no usa el LLM ni el
intérprete de CR-BioLM (L2, con costo). Se puede reemplazar por uno mejor sin
tocar el resto, porque solo se usa a través de `analizar`.

Regla:
- Geoespacial si menciona algo geográfico (dónde, distribución, altitud,
  provincia, mapa...).
- NO geoespacial solo si pregunta por algo descriptivo (hojas, flores, color,
  familia, usos...) y nada geográfico. Así se evita pedir GBIF y el mapa cuando
  no aportan, y la respuesta llega antes.
- Cualquier otro caso, incluido el nombre de la especie solo, es geoespacial:
  es el caso principal del prototipo y se responde con todo.

Las palabras se comparan sin tildes y en minúscula.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Palabras que piden información geográfica.
GEOESPACIALES = frozenset(
    {
        # dónde está
        "donde", "distribucion", "distribuye", "distribuida", "distribuido",
        "crece", "crecen", "habita", "habitan", "habitat", "encuentra", "encuentran",
        "ubicacion", "ubica", "ubicada", "ubicado", "localidad", "localidades",
        "lugar", "lugares", "zona", "zonas", "sitio", "sitios",
        "nativa", "nativo", "endemica", "endemico",
        # registros y mapa
        "mapa", "mapas", "coordenadas", "registros", "registro", "ocurrencias",
        "presencia", "avistamientos", "gbif",
        # altitud
        "altitud", "altitudes", "elevacion", "elevaciones", "altura", "msnm",
        # geografía de Costa Rica
        "region", "regiones", "provincia", "provincias", "canton", "cantones",
        "vertiente", "vertientes", "caribe", "pacifico", "cordillera", "volcan",
        "parque", "parques", "reserva", "reservas", "protegida", "protegidas",
        "bosque", "bosques", "llanura", "valle",
        "alajuela", "cartago", "heredia", "guanacaste", "puntarenas", "limon",
        "talamanca", "monteverde", "osa", "tilaran",
    }
)  # fmt: skip

# Palabras que preguntan cómo es la planta, no dónde está.
DESCRIPTIVAS = frozenset(
    {
        "hoja", "hojas", "flor", "flores", "fruto", "frutos", "semilla", "semillas",
        "tallo", "tallos", "tronco", "corteza", "raiz", "raices", "petalos",
        "inflorescencia", "inflorescencias", "floracion", "florece", "florecen",
        "color", "colores", "forma", "tamano", "mide", "miden", "aspecto",
        "apariencia", "caracteristicas", "describe", "descripcion", "morfologia",
        "identificar", "reconocer", "distinguir", "familia", "genero",
        "uso", "usos", "sirve", "toxica", "toxico", "comestible", "medicinal",
    }
)  # fmt: skip

# Palabras que no preguntan nada por sí solas ("información sobre ...").
GENERICAS = frozenset(
    {
        "a", "al", "de", "del", "el", "la", "las", "los", "lo", "un", "una", "y", "o",
        "en", "con", "por", "para", "que", "cual", "cuales", "como", "es", "son",
        "me", "mi", "se", "su", "sus", "sobre", "acerca", "hay", "tiene",
        "informacion", "info", "datos", "dato", "ficha", "todo", "toda",
        "hablame", "cuentame", "dime", "muestrame", "quiero", "saber", "ver",
        "conocer", "busco", "buscar", "planta", "plantas", "especie", "especies",
        "arbol", "arboles", "var", "subsp",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Intencion:
    geoespacial: bool  # RR_41: pedir los registros de GBIF y el mapa
    pregunta_especifica: bool  # pregunta algo además del nombre de la especie (RR_44)


def analizar(texto: str, especie: str = "") -> Intencion:
    """Qué pide `texto` sobre `especie` (ver las reglas al inicio del módulo)."""
    propias = set(palabras(especie))
    resto = [p for p in palabras(texto) if p not in propias and p not in GENERICAS]
    geografica = any(p in GEOESPACIALES for p in resto)
    descriptiva = any(p in DESCRIPTIVAS for p in resto)
    return Intencion(
        geoespacial=geografica or not descriptiva,
        pregunta_especifica=bool(resto),
    )


def palabras(texto: str) -> list[str]:
    """'¿Dónde CRECE?' -> ['donde', 'crece']: minúsculas, sin tildes ni signos."""
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", sin_tildes)
