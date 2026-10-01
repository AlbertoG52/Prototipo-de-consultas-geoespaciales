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


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres: 'Guaría' encuentra 'guaria'.

    Solo sirve para comparar; el texto que se guarda o se muestra conserva sus
    tildes.
    """
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
