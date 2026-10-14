"""Qué pide la consulta — RR_41 criterio 1 y RR_29. PROVISIONAL.

Clasifica la pregunta por su tipo (`TipoPregunta`) y dice si pregunta algo
concreto además del nombre de la especie (para RR_44, el fragmento del Manual
que lo responde).

Es un clasificador por palabras clave, a propósito simple: no usa el LLM ni el
intérprete de CR-BioLM (L2, con costo). Se puede reemplazar por uno mejor sin
tocar el resto, porque solo se usa a través de `analizar`.

Tipos, en orden de prioridad (la primera lista que coincide gana):

    DISTRIBUCION  algo geográfico: dónde, distribución, altitud, provincia, mapa...
    HABITAT       en qué ambiente vive: hábitat, tipo de bosque, páramo, epífita...
                  (RR_29, lista HABITAT más los tipos de bosque del vocabulario
                  de CR-BioLM)
    DISTRIBUCION  "crece" o "se encuentra" sin nada de lo anterior
    DESCRIPCION   cómo es la planta: hojas, flores, color, familia, usos...
    GENERAL       nada de lo anterior, p. ej. solo el nombre de la especie

"Crece" y "se encuentra" (VERBOS_DE_LUGAR) van después de HABITAT: "¿En qué
bosque crece?" pregunta por el hábitat, "¿Dónde crece?" por la distribución.

Qué decide el tipo:
- El texto de la respuesta (services/contexto_especie.py): distribución,
  hábitat (RR_29) o morfología.
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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..dominio import TipoPregunta

# Palabras que piden información geográfica. Las de hábitat ("hábitat",
# "bosque") pasaron a HABITAT con RR_29.
GEOESPACIALES = frozenset(
    {
        # dónde está
        "donde", "distribucion", "distribuye", "distribuida", "distribuido",
        "crece", "crecen", "encuentra", "encuentran",
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
        "llanura", "valle",
        "alajuela", "cartago", "heredia", "guanacaste", "puntarenas", "limon",
        "talamanca", "monteverde", "osa", "tilaran",
    }
)  # fmt: skip

# Verbos geográficos que, junto a una palabra de hábitat, preguntan por el
# hábitat: "¿En qué bosque crece?" (ver la prioridad al inicio del módulo).
VERBOS_DE_LUGAR = frozenset({"crece", "crecen", "encuentra", "encuentran"})

# RR_29: palabras que preguntan en qué ambiente vive la planta. Una pregunta de
# hábitat sigue trayendo GBIF y mapa; cambia el texto (ContextoEspecie._texto).
# "Seco" y "húmedo" solos no cuentan ("¿florece en la época seca?"): "bosque
# seco" ya cuenta por "bosque".
HABITAT = frozenset(
    {
        "habitat", "habitats", "habita", "habitan", "ambiente", "ambientes",
        "ecosistema", "ecosistemas", "bosque", "bosques", "selva", "selvas",
        "sotobosque", "dosel", "robledal", "robledales", "manglar", "manglares",
        "paramo", "paramos", "subparamo", "pluvial", "pluviales", "nuboso", "nubosos",
        "nubosa", "matorral", "matorrales", "pantano", "pantanos", "humedal",
        "humedales", "epifita", "epifitas", "hemiepifita", "hemiepifitas",
        "terrestre", "terrestres", "acuatica", "acuaticas", "parasita", "parasitas",
        "sombra", "suelo", "suelos",
    }
)  # fmt: skip

# Tipos de bosque del vocabulario de CR-BioLM que solos son ambiguos: "roble"
# es parte de nombres comunes ("roble negro"); "seco" y "húmedo", ver HABITAT.
_TIPOS_DE_BOSQUE_AMBIGUOS = frozenset({"roble", "seco", "humedo", "muy"})

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


# TipoPregunta vive en dominio.py (se guarda en la BD, RR_33); se importa
# arriba, así que `from .intencion import TipoPregunta` sigue funcionando.

# La primera lista que coincide decide el tipo (ver el inicio del módulo).
_PRIORIDAD = (
    (TipoPregunta.DISTRIBUCION, GEOESPACIALES - VERBOS_DE_LUGAR),
    (TipoPregunta.HABITAT, HABITAT),
    (TipoPregunta.DISTRIBUCION, VERBOS_DE_LUGAR),
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


def analizar(
    texto: str, especie: str = "", vocabulario: Mapping[str, Any] | None = None
) -> Intencion:
    """Qué pide `texto` sobre `especie` (ver las reglas al inicio del módulo).

    RR_29: `vocabulario` es el de get_vocabulary de CR-BioLM; sus tipos de bosque
    también cuentan como palabras de hábitat. Sin él (catálogo de demostración,
    o CR-BioLM no lo dio) se usa solo la lista HABITAT.
    """
    propias = set(palabras(especie))
    resto = [p for p in palabras(texto) if p not in propias and p not in GENERICAS]
    de_bosque = tipos_de_bosque(vocabulario)
    tipo = next(
        (
            tipo
            for tipo, lista in _PRIORIDAD
            if any(p in lista or (tipo is TipoPregunta.HABITAT and p in de_bosque) for p in resto)
        ),
        TipoPregunta.GENERAL,
    )
    return Intencion(tipo=tipo, pregunta_especifica=bool(resto))


def tipos_de_bosque(vocabulario: Mapping[str, Any] | None) -> frozenset[str]:
    """RR_29: las palabras de los tipos de bosque del Manual ('páramo' -> 'paramo').

    Sin las ambiguas (_TIPOS_DE_BOSQUE_AMBIGUOS) ni las genéricas: de 'muy
    húmedo' no queda ninguna.
    """
    tipos = (vocabulario or {}).get("forest_types") or []
    descartadas = GENERICAS | _TIPOS_DE_BOSQUE_AMBIGUOS
    return frozenset(p for tipo in tipos for p in palabras(str(tipo)) if p not in descartadas)


def palabras(texto: str) -> list[str]:
    """'¿Dónde CRECE?' -> ['donde', 'crece']: minúsculas, sin tildes ni signos."""
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", sin_tildes)
