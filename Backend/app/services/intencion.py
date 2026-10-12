"""Qué pide la consulta — RR_41 criterio 1. PROVISIONAL.

Clasifica la pregunta por su tipo (`TipoPregunta`) y dice si pregunta algo
concreto además del nombre de la especie (para RR_44, el fragmento del Manual
que lo responde).

Es un clasificador por palabras clave, a propósito simple: no usa el LLM ni el
intérprete de CR-BioLM (L2, con costo). Se puede reemplazar por uno mejor sin
tocar el resto, porque solo se usa a través de `analizar`.

Tipos, en orden de prioridad (la primera lista que coincide gana):

    DISTRIBUCION  algo geográfico: dónde, distribución, altitud, provincia, mapa...
    HABITAT       en qué ambiente vive (RR_29, lista HABITAT; ver abajo)
    DESCRIPCION   cómo es la planta: hojas, flores, color, familia, usos...
    GENERAL       nada de lo anterior, p. ej. solo el nombre de la especie

Qué decide el tipo:
- El texto de la respuesta (services/contexto_especie.py): distribución,
  morfología o, cuando esté, el texto de hábitat de RR_29.
- `geoespacial` (RR_41): si la pregunta pide información geográfica. Solo una
  pregunta DESCRIPCION no la pide.

Qué NO decide: si se piden los registros de GBIF y el mapa. Se piden siempre
que existan, porque RR_52 (criterio 3), RR_46 (criterio 1) y RR_59 piden
mostrar la distribución y la cantidad de registros cuando hay datos.

Las palabras se comparan sin tildes y en minúscula.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

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

# RR_29 (Cristopher): palabras que preguntan en qué ambiente vive la planta
# (hábitat, tipo de bosque...). Vacía por ahora: al llenarla, sacar esas
# palabras de GEOESPACIALES y dar el texto de hábitat en
# ContextoEspecie._texto. Una pregunta de hábitat sigue trayendo GBIF y mapa.
HABITAT: frozenset[str] = frozenset()

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


class TipoPregunta(StrEnum):
    """Qué pregunta la consulta (ver la prioridad al inicio del módulo)."""

    DISTRIBUCION = "distribucion"
    HABITAT = "habitat"  # RR_29
    DESCRIPCION = "descripcion"
    GENERAL = "general"


# La primera lista que coincide decide el tipo.
_PRIORIDAD = (
    (TipoPregunta.DISTRIBUCION, GEOESPACIALES),
    (TipoPregunta.HABITAT, HABITAT),
    (TipoPregunta.DESCRIPCION, DESCRIPTIVAS),
)


@dataclass(frozen=True)
class Intencion:
    tipo: TipoPregunta
    pregunta_especifica: bool  # pregunta algo además del nombre de la especie (RR_44)

    @property
    def geoespacial(self) -> bool:
        """RR_41 criterio 1: la pregunta pide información geográfica."""
        return self.tipo is not TipoPregunta.DESCRIPCION


def analizar(texto: str, especie: str = "") -> Intencion:
    """Qué pide `texto` sobre `especie` (ver las reglas al inicio del módulo)."""
    propias = set(palabras(especie))
    resto = [p for p in palabras(texto) if p not in propias and p not in GENERICAS]
    tipo = next(
        (tipo for tipo, lista in _PRIORIDAD if any(p in lista for p in resto)),
        TipoPregunta.GENERAL,
    )
    return Intencion(tipo=tipo, pregunta_especifica=bool(resto))


def palabras(texto: str) -> list[str]:
    """'¿Dónde CRECE?' -> ['donde', 'crece']: minúsculas, sin tildes ni signos."""
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", sin_tildes)
