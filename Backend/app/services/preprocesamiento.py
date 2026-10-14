"""Mensajes que no son una consulta — RR_22, RR_32, RR_37 y RR_40.

`interpretar(texto)` se usa ANTES de buscar especies. Si el mensaje no es una
consulta que se pueda procesar, devuelve el motivo (MotivoOrientacion) y
services/consultas.py responde orientando al usuario: no busca especies, no
llama a CR-BioLM y no descuenta del límite diario. Se revisa en este orden:

1. RR_32 sin sentido: no tiene letras ("123", "???") o ninguna de sus palabras
   se puede pronunciar (sin vocales o con cinco consonantes seguidas: "asdfgh").
2. RR_22 idioma: es claramente inglés (al menos dos palabras típicas del
   inglés y más que del español). Ante la duda, sigue: los nombres científicos
   están en latín y no cuentan para ningún idioma.
3. RR_40 ayuda: trae una frase de ayuda ("¿qué puedo preguntar?", "¿cómo
   funciona?") y nada más que cortesía o palabras sobre el agente y sus fuentes
   ("¿Qué puedo hacer con el manual de plantas?"). "¿Para qué sirve la guaria
   morada?" sí es una consulta: sobra el nombre de la planta.
4. RR_37 saludo: solo trae cortesía ("hola", "gracias", "¿qué tal todo?").

`fuera_de_tema(texto)` se usa DESPUÉS de buscar, cuando no se reconoció ninguna
especie (RR_37): si además ninguna palabra tiene que ver con plantas, geografía
o descripción, el mensaje no es sobre flora. Antes de buscar no se puede saber:
"guaria morada" no tiene ninguna de esas palabras y es una planta. Por eso su
mensaje sugiere probar con el nombre científico.

Todo es por palabras clave, sin LLM, comparadas sin tildes ni mayúsculas
(intencion.palabras, RR_35), igual que services/intencion.py.
"""

from __future__ import annotations

import re

from .. import config
from ..dominio import MotivoOrientacion
from . import intencion
from .contexto_especie import GBIF, MANUAL
from .intencion import GENERICAS, palabras

# --- RR_32: sin sentido ---------------------------------------------------------

_VOCALES = frozenset("aeiouy")
_CINCO_CONSONANTES = re.compile(r"[b-df-hj-np-tv-xz]{5}")
_LETRA = re.compile(r"[^\W\d_]")


def _impronunciable(palabra: str) -> bool:
    return not (_VOCALES & set(palabra)) or bool(_CINCO_CONSONANTES.search(palabra))


def _es_sin_sentido(texto: str, sus_palabras: list[str]) -> bool:
    if not _LETRA.search(texto) or not sus_palabras:
        return True
    return all(_impronunciable(p) for p in sus_palabras)


# --- RR_22: idioma ----------------------------------------------------------------

# Palabras frecuentes del inglés que no se usan en español. Sin "a", "me" ni
# "no", que existen en los dos.
_INGLES = frozenset(
    {
        "the", "what", "where", "which", "who", "why", "how", "is", "are", "was",
        "were", "does", "did", "can", "could", "would", "should", "will", "of", "in",
        "on", "and", "or", "for", "to", "with", "from", "about", "this", "that",
        "these", "there", "it", "its", "my", "your", "you", "i", "tell", "show",
        "please", "grow", "grows", "growing", "found", "find", "live", "lives",
        "located", "plant", "plants", "tree", "trees", "flower", "flowers", "leaf",
        "leaves", "species", "hello", "hi", "thanks", "thank", "help",
    }
)  # fmt: skip

_ESPANOL = frozenset(
    {
        "de", "del", "la", "el", "los", "las", "que", "donde", "como", "cual", "cuales",
        "en", "es", "son", "un", "una", "por", "para", "con", "se", "y", "al", "lo",
        "me", "mi", "su", "muy", "mas", "hay", "esta", "estan", "tiene", "crece",
        "crecen", "vive", "habita", "encuentra", "planta", "plantas", "arbol", "hoja",
        "hojas", "flor", "flores", "especie", "especies", "sobre", "hola", "gracias",
        "puedo", "quiero", "ayuda",
    }
)  # fmt: skip

# Con cualquiera de estos caracteres el texto ya es español.
_MARCAS_DEL_ESPANOL = frozenset("¿¡ñáéíóúü")


def _es_ingles(texto: str, sus_palabras: list[str]) -> bool:
    if _MARCAS_DEL_ESPANOL & set(texto.lower()):
        return False
    ingles = sum(p in _INGLES for p in sus_palabras)
    espanol = sum(p in _ESPANOL for p in sus_palabras)
    return ingles >= 2 and ingles > espanol


# --- RR_37 y RR_40: cortesía y ayuda ----------------------------------------------

_SALUDOS = frozenset({"hola", "holi", "holis", "buenas", "buenos", "buen", "dias", "tardes",
                      "noches", "saludos", "hey", "hello", "hi", "tal", "pura"})  # fmt: skip
_AGRADECIMIENTOS = frozenset({"gracias", "thanks", "agradezco", "ok", "okay", "vale",
                              "genial", "perfecto", "excelente", "listo", "entendido"})  # fmt: skip
_DESPEDIDAS = frozenset({"adios", "chao", "chau", "bye", "luego", "pronto", "vemos"})
_CORTESIA = _SALUDOS | _AGRADECIMIENTOS | _DESPEDIDAS

# Palabras que acompañan a la cortesía sin agregar ninguna pregunta.
_RELLENO = frozenset(
    {
        "como", "estas", "esta", "estan", "todo", "toda", "bien", "muy", "muchas",
        "muchisimas", "mucho", "mil", "alla", "aca", "aqui", "tu", "usted", "te",
        "le", "amigo", "amiga", "nada", "igualmente", "igual", "gusto", "hasta",
        "nos", "vida", "otra", "vez", "porfa", "favor", "puedes", "puede", "podes",
        "podrias", "dame", "quisiera", "necesito", "explicame", "explica", "usar",
        "usarlo", "usarte", "uso",
    }
)  # fmt: skip

# Verbos que quedan sueltos en un pedido de ayuda ("¿qué consultas puedo hacer?").
_VERBOS_DE_AYUDA = frozenset({"puedo", "podemos", "hacer", "preguntar", "preguntarte",
                              "consultar", "funciona", "sirve", "sirves"})  # fmt: skip

# Palabras sobre el agente y sus fuentes: pueden acompañar a un pedido de ayuda.
_SISTEMA = frozenset(
    {
        "manual", "manuales", "agente", "bot", "chatbot", "florabot", "cr", "asistente",
        "sistema", "aplicacion", "app", "pagina", "web", "chat", "herramienta",
        "programa", "plataforma", "servicio", "prototipo", "esto", "este", "eso",
        "contigo", "ti", "vos", "fuente", "fuentes", "base", "gbif", "mapa", "mapas",
        "flora", "costa", "rica", "pregunta", "preguntas", "consulta", "consultas",
    }
)  # fmt: skip

# Frases que piden ayuda, sobre las palabras ya normalizadas.
_FRASES_DE_AYUDA = [
    re.compile(rf"\b{frase}\b")
    for frase in (
        r"ayuda(?:me|nos)?",
        r"ayudeme",
        r"ayudar(?:me)?",
        r"help",
        # "¿qué puedo preguntar?", "¿qué plantas puedo consultar del manual?"
        r"(?:que|como|para que) (?:mas )?(?:plantas |especies |cosas |temas |datos )?"
        r"(?:te |le |se |lo )?(?:puedo|puede|puedes|podes|podria|podemos|pueden) "
        r"(?:hacer|preguntar|preguntarte|consultar|consultarte|buscar|usar|usarte|"
        r"pedir|pedirte|saber|ver)",
        r"que (?:tipo |tipos |clase )?(?:de )?(?:preguntas|consultas)",
        # "¿qué especies hay en el manual?", "¿qué plantas conoces?"
        r"que (?:plantas|especies) (?:hay|tiene|tienes|tienen|incluye|incluyes|conoces|abarca)",
        r"como funcionas?",
        r"como (?:se |te |lo |la )?usa?",
        r"como (?:te |lo |la )?uso",
        r"que (?:haces|sabes(?: hacer)?|eres)",
        r"para que (?:sirves|sirve)",
        r"quien eres",
        r"instrucciones",
        r"ejemplos?",
        r"menu",
        r"opciones",
    )
]


def _pide_ayuda(sus_palabras: list[str]) -> bool:
    frase = " ".join(sus_palabras)
    if not any(patron.search(frase) for patron in _FRASES_DE_AYUDA):
        return False
    for patron in _FRASES_DE_AYUDA:
        frase = patron.sub(" ", frase)
    permitidas = _CORTESIA | _RELLENO | _VERBOS_DE_AYUDA | _SISTEMA | GENERICAS
    return all(p in permitidas for p in frase.split())


def _es_saludo(sus_palabras: list[str]) -> bool:
    permitidas = _CORTESIA | _RELLENO | GENERICAS
    return any(p in _CORTESIA for p in sus_palabras) and all(p in permitidas for p in sus_palabras)


# --- RR_37: fuera de tema -----------------------------------------------------------

# Palabras sobre plantas que no están en las listas de services/intencion.py.
_FLORA = frozenset(
    {
        "planta", "plantas", "arbol", "arboles", "arbusto", "arbustos", "hierba",
        "hierbas", "orquidea", "orquideas", "helecho", "helechos", "palma", "palmas",
        "palmera", "palmeras", "bejuco", "bejucos", "liana", "lianas", "epifita",
        "epifitas", "musgo", "musgos", "cactus", "bromelia", "bromelias", "especie",
        "especies", "familia", "botanica", "botanico", "flora", "vegetal", "vegetales",
        "vegetacion", "madera", "maderable", "selva", "manglar", "manglares", "jardin",
        "cultivo", "cultiva", "cultivar", "sembrar", "siembra", "silvestre", "nombre",
        "cientifico", "cientifica", "comun", "taxon", "var", "subsp",
    }
)  # fmt: skip


def fuera_de_tema(texto: str) -> bool:
    """RR_37: ninguna palabra del texto tiene que ver con plantas (ver el módulo).

    Usa las listas de services/intencion.py en el momento de llamarla, así que
    incluye lo que RR_29 agregue a HABITAT.
    """
    sobre_plantas = _FLORA | intencion.GEOESPACIALES | intencion.HABITAT | intencion.DESCRIPTIVAS
    return not any(p in sobre_plantas for p in palabras(texto))


# --- qué se responde ------------------------------------------------------------------


def interpretar(texto: str) -> MotivoOrientacion | None:
    """Por qué `texto` no es una consulta procesable, o None si lo es (ver el módulo)."""
    sus_palabras = palabras(texto)
    if _es_sin_sentido(texto, sus_palabras):
        return MotivoOrientacion.SIN_SENTIDO
    if _es_ingles(texto, sus_palabras):
        return MotivoOrientacion.IDIOMA
    if _pide_ayuda(sus_palabras):
        return MotivoOrientacion.AYUDA
    if _es_saludo(sus_palabras):
        return MotivoOrientacion.SALUDO
    return None


# RR_40 criterio 3: consultas válidas con nombre científico, que funcionan con el
# catálogo de demostración y con el de CR-BioLM (los nombres comunes todavía no
# los reconoce CR-BioLM, RR_25). Cada especie debe estar en los dos: el Manual de
# CR-BioLM no tiene Cedrela odorata, por eso se usa C. tonduzii.
EJEMPLOS_DE_CONSULTA = (
    "¿Dónde crece Quercus costaricensis?",
    "¿Cómo son las hojas de Cedrela tonduzii?",
    "¿En qué tipo de bosque vive Bactris gasipaes?",
)

_QUE_SE_PUEDE_PREGUNTAR = (
    "Puedo contarte dónde crece una planta de Costa Rica, en qué hábitat vive o cómo es. "
    "Escribe su nombre común o científico."
)

_MENSAJES = {
    MotivoOrientacion.SIN_SENTIDO: (
        "No logré entender tu consulta. ¿Puedes escribirla de otra forma? "
        "Pregunta por una planta de Costa Rica usando su nombre común o científico."
    ),
    MotivoOrientacion.IDIOMA: (
        "Por ahora solo puedo responder consultas en español (only Spanish is supported "
        "for now). Escribe tu pregunta en español, por ejemplo: "
        f"«{EJEMPLOS_DE_CONSULTA[0]}»"
    ),
    MotivoOrientacion.AYUDA: (
        "Puedo responder preguntas sobre la flora de Costa Rica:\n"
        f"• Distribución: dónde crece una especie, con su mapa y los registros de {GBIF}.\n"
        "• Hábitat: en qué tipo de bosque o ambiente vive.\n"
        "• Descripción: cómo es (hojas, flores, familia…).\n"
        "Escribe en español, con el nombre común o científico de la planta (hasta "
        f"{config.LONGITUD_MAXIMA_CONSULTA} caracteres). Los datos vienen del {MANUAL} y "
        f"de {GBIF}."
    ),
    MotivoOrientacion.FUERA_DE_TEMA: (
        "No reconocí ninguna planta en tu mensaje. Puedo responder preguntas sobre la "
        "flora de Costa Rica: dónde crece una especie, su hábitat o cómo es. Si "
        "mencionaste una planta, prueba con su nombre científico."
    ),
}


def mensaje_de(motivo: MotivoOrientacion, texto: str) -> str:
    """Lo que se le responde al usuario (RR_37 y RR_40 criterio 2, RR_22 criterio 2...)."""
    if motivo is not MotivoOrientacion.SALUDO:
        return _MENSAJES[motivo]
    sus_palabras = set(palabras(texto))
    if sus_palabras & _DESPEDIDAS:
        return f"¡Hasta pronto! Cuando quieras, vuelve a preguntar. {_QUE_SE_PUEDE_PREGUNTAR}"
    if sus_palabras & _AGRADECIMIENTOS:
        return f"¡Con gusto! {_QUE_SE_PUEDE_PREGUNTAR}"
    return f"¡Hola! {_QUE_SE_PUEDE_PREGUNTAR}"
