"""Sanitización de las entradas de texto — RR_00_08.

Todo texto libre que llega del usuario pasa por `sanitizar_texto` en los
esquemas de Pydantic, antes de que cualquier router lo procese.

Qué se neutraliza:

- Caracteres de control (U+0000–U+001F, U+007F–U+009F) salvo salto de línea y
  tabulador. El byte nulo en particular hace que PostgreSQL rechace la
  inserción y la petición termine en un error 500.
- Caracteres de formato invisibles (categoría Unicode "Cf"): espacios de ancho
  cero y marcas de dirección como U+202E, que permiten ocultar o invertir
  visualmente parte del texto.
- Etiquetas HTML o XML completas (`<script>`, `<img ...>`, `</b>`). Si el texto
  se muestra algún día fuera de React (un correo, un PDF exportado, un panel
  de administración), ya no lleva marcado ejecutable.

Qué NO se toca, para no alterar contenido legítimo (criterio 3):

- Tildes, ñ, diéresis y signos de apertura. El texto se normaliza a NFC, que
  cambia la representación interna pero no lo que se lee.
- Comillas, apóstrofos, punto y coma, guiones: son comunes en nombres de
  especies y en preguntas. La inyección SQL ya está cubierta porque SQLAlchemy
  parametriza todas las consultas; eliminar esos caracteres solo rompería
  entradas válidas.
- Los signos "<" y ">" sueltos ("elevación > 1000"): solo se eliminan cuando
  forman una etiqueta, es decir, cuando "<" va seguido de una letra, "/" o "!".

El backend no ejecuta comandos del sistema con entradas del usuario. Si en el
futuro el texto se pasa a un proceso externo o a un modelo de lenguaje, esta
función no sustituye el escapado propio de ese destino.

Las contraseñas no se sanitizan: cualquier cambio alteraría la credencial. Se
guardan solo como hash y nunca se muestran.

El texto de una consulta pasa además por `limpiar_consulta` (RR_21), que quita
lo que sobra para interpretarla, y se compara con `normalizar` (RR_35).
"""

from __future__ import annotations

import re
import unicodedata

# Una etiqueta empieza con "<" seguido de una letra, "/" o "!" (comentarios y
# DOCTYPE) y termina en el primer ">". Así "a < b > c" no se considera etiqueta.
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

    # Se repite hasta que no quede ninguna etiqueta: una entrada como
    # "<scr<b>ipt>" formaría una nueva etiqueta tras una sola pasada.
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _ETIQUETA.sub("", texto)

    return texto.strip()


# --- RR_21: limpieza del texto de una consulta -----------------------------------

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
    """RR_21: el texto de la consulta sin espacios ni caracteres innecesarios.

    Se aplica después de `sanitizar_texto`. Quita:

    - emojis y otros símbolos decorativos (se cambian por un espacio, para no
      pegar las palabras que separaban),
    - espacios, tabuladores y saltos de línea repetidos (queda uno),
    - espacios junto a los signos ("¿ dónde ?" -> "¿dónde?"),
    - signos repetidos ("??", "!!!", ",,") y más de tres puntos seguidos.

    Conserva el significado (criterio 2): no cambia mayúsculas, tildes, ñ,
    números ni los signos de comparación ("> 1000 m"). La comparación sin tildes
    ni mayúsculas es aparte (`normalizar`, RR_35), para que el texto guardado y
    mostrado siga igual a como se escribió. Aplicarla dos veces no cambia nada.
    """
    texto = "".join(" " if _es_simbolo_decorativo(c) else c for c in texto)
    texto = _ESPACIOS.sub(" ", texto)
    texto = _ESPACIO_TRAS_APERTURA.sub(r"\1", texto)
    texto = _ESPACIO_ANTES_DE_CIERRE.sub(r"\1", texto)
    texto = _SIGNO_REPETIDO.sub(r"\1", texto)
    texto = _PUNTOS.sub("...", texto)
    return texto.strip()


def normalizar(texto: str) -> str:
    """RR_35: minúsculas y sin tildes, para comparar: 'Guaría' encuentra 'guaria'.

    Toda búsqueda de especies compara con esta función (catálogo, sugerencias),
    así que ni las tildes ni las mayúsculas cambian el resultado. Solo sirve
    para comparar; el texto que se guarda o se muestra conserva sus tildes.
    """
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
