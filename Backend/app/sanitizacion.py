"""Sanitización y limpieza de los textos que llegan del usuario.

`sanitizar_texto` se aplica en los esquemas de Pydantic. Quita caracteres de control (salvo
salto de línea y tabulador), caracteres invisibles (espacios de ancho cero, U+202E) y
etiquetas HTML completas. Conserva tildes, ñ, comillas, punto y coma y los signos "<" y ">"
sueltos; la inyección SQL ya la evita SQLAlchemy al parametrizar las consultas.

Las contraseñas no se sanitizan: se guardan solo como hash.

El texto de una consulta pasa además por `limpiar_consulta`, y las búsquedas comparan con
`normalizar`.
"""

from __future__ import annotations

import re
import unicodedata

# Una etiqueta empieza con "<" seguido de una letra, "/" o "!" y termina en el primer ">".
# Así "a < b > c" no se considera etiqueta.
_ETIQUETA = re.compile(r"<[/!]?[A-Za-z][^<>]*>|<!--.*?-->", re.DOTALL)

_PERMITIDOS = {"\n", "\t"}


def _es_invisible_o_control(caracter: str) -> bool:
    if caracter in _PERMITIDOS:
        return False
    return unicodedata.category(caracter) in ("Cc", "Cf")


def sanitizar_texto(valor: str) -> str:
    """Devuelve el texto sin caracteres de control, invisibles ni etiquetas.

    El resultado puede quedar vacío si la entrada solo contenía marcado o
    caracteres invisibles; el esquema que llama decide si eso es un error.
    """
    texto = unicodedata.normalize("NFC", valor)
    texto = "".join(c for c in texto if not _es_invisible_o_control(c))

    # Se repite hasta que no quede ninguna etiqueta: "<scr<b>ipt>" formaría una nueva tras
    # una sola pasada.
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _ETIQUETA.sub("", texto)

    return texto.strip()


# --- limpieza del texto de una consulta -----------------------------------------

# Símbolos que se conservan aunque Unicode los clasifique como "otro símbolo".
_SIMBOLOS_CON_SENTIDO = {"°"}  # 9°N, 25 °C

_ESPACIOS = re.compile(r"\s+")
# Espacio sobrante después de un signo de apertura o antes de uno de cierre:
# "¿ dónde crece ?" -> "¿dónde crece?".
_ESPACIO_TRAS_APERTURA = re.compile(r"([¿¡(])\s+")
_ESPACIO_ANTES_DE_CIERRE = re.compile(r"\s+([?!.,;:)])")
# Un signo repetido no cambia la pregunta: "¿¿dónde??!!" -> "¿dónde?!".
_SIGNO_REPETIDO = re.compile(r"([¿?¡!,;:])\1+")
# Cuatro o más puntos seguidos quedan en puntos suspensivos.
_PUNTOS = re.compile(r"\.{4,}")


def _es_simbolo_decorativo(caracter: str) -> bool:
    """Emojis, pictogramas y modificadores (🌿, ★, 👍🏽): no forman parte de la pregunta."""
    if caracter in _SIMBOLOS_CON_SENTIDO:
        return False
    if "︀" <= caracter <= "️":  # selectores de variación de los emojis
        return True
    return unicodedata.category(caracter) in ("So", "Sk")


def limpiar_consulta(texto: str) -> str:
    """Texto de la consulta sin espacios ni caracteres innecesarios.

    Quita emojis y símbolos decorativos, espacios repetidos, espacios junto a los signos
    ("¿ dónde ?" -> "¿dónde?") y signos repetidos ("??", "!!!"). No cambia mayúsculas,
    tildes, ñ, números ni signos de comparación ("> 1000 m"). Aplicarla dos veces no cambia
    nada.
    """
    texto = "".join(" " if _es_simbolo_decorativo(c) else c for c in texto)
    texto = _ESPACIOS.sub(" ", texto)
    texto = _ESPACIO_TRAS_APERTURA.sub(r"\1", texto)
    texto = _ESPACIO_ANTES_DE_CIERRE.sub(r"\1", texto)
    texto = _SIGNO_REPETIDO.sub(r"\1", texto)
    texto = _PUNTOS.sub("...", texto)
    return texto.strip()


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar: 'Guaría' encuentra 'guaria'.

    Solo se usa para comparar; el texto que se guarda o se muestra conserva sus tildes.
    """
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


# Una palabra del texto: letras y guiones (el mismo criterio que buscar_especies).
_PALABRA = re.compile(r"[^\W\d_][\w-]*")


def con_nombre_canonico(texto: str, nombre: str) -> str:
    """Devuelve `texto` con el nombre de la especie escrito como en el catálogo.

    "¿Dónde crece QUÉRCUS costaricénsis?" -> "¿Dónde crece Quercus costaricensis?". Se usa
    en la pregunta que se envía a CR-BioLM, que distingue mayúsculas y tildes. Si el nombre
    no aparece, el texto queda igual.
    """
    buscadas = _PALABRA.findall(normalizar(nombre))
    palabras = list(_PALABRA.finditer(texto))
    n = len(buscadas)
    for i in range(len(palabras) - n + 1):
        ventana = palabras[i : i + n]
        if [normalizar(p.group()) for p in ventana] == buscadas:
            # Se reemplaza del inicio de la primera palabra al fin de la última, así
            # que un "var." en medio también queda como en el catálogo.
            inicio, fin = ventana[0].start(), ventana[-1].end()
            return texto[:inicio] + nombre + texto[fin:]
    return texto
