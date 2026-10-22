"""Pruebas de RR_21 (limpieza), RR_34 (límite de longitud) y RR_35 (acentos y
mayúsculas) del texto de una consulta.

Solo las que pasan por la API (las marcadas con `visitante`) necesitan la BD.
Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from pydantic import ValidationError

from app import config
from app.sanitizacion import con_nombre_canonico, limpiar_consulta, normalizar
from app.schemas.consulta import ConsultaRequest
from app.services.catalogo import CatalogoDemo
from app.services.intencion import analizar

from apoyo import api

catalogo = CatalogoDemo()


# --- RR_21 criterio 1: se quitan espacios y caracteres innecesarios -------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("  ¿Dónde   crece    el pejibaye?  ", "¿Dónde crece el pejibaye?"),
        ("¿Dónde crece\n\nel\tpejibaye?", "¿Dónde crece el pejibaye?"),
        ("¿ Dónde crece el pejibaye ?", "¿Dónde crece el pejibaye?"),
        ("¿¿Dónde crece el pejibaye???", "¿Dónde crece el pejibaye?"),
        ("¡¡Hola!! ¿dónde crece?!", "¡Hola! ¿dónde crece?!"),
        ("cedro amargo,, roble", "cedro amargo, roble"),
        ("guaria morada.......", "guaria morada..."),
        ("🌿 ¿Dónde crece la guaria morada? 🌸🌸", "¿Dónde crece la guaria morada?"),
        ("guaria🌸morada", "guaria morada"),
        ("pejibaye ★ 👍🏽", "pejibaye"),
        ("❤️ cedro", "cedro"),  # emoji con selector de variación
    ],
)
def test_quita_espacios_y_caracteres_innecesarios(entrada, esperado):
    assert limpiar_consulta(entrada) == esperado


# --- RR_21 criterio 2: se conserva el significado --------------------------------


@pytest.mark.parametrize(
    "entrada",
    [
        "¿Dónde se encuentra la guaria morada?",
        "Especies con elevación > 1000 y < 2500 msnm",
        "Plantas a 9°N en Guanacaste",
        "¿Qué es el \"cedro amargo\"; y el 'cedro dulce'?",
        "Pingüino, año, ñandú",
        "Inga edulis var. minutula (Fabaceae)",
        "¿Dónde crece? ¿Y a qué altura?",
        "Lo vi en Monteverde...",
    ],
)
def test_no_altera_una_consulta_ya_limpia(entrada):
    assert limpiar_consulta(entrada) == entrada


def test_no_cambia_mayusculas_ni_tildes():
    # La comparación sin tildes es aparte (RR_35); el texto guardado no cambia.
    assert limpiar_consulta("CEDRO Amargo en LIMÓN") == "CEDRO Amargo en LIMÓN"


@pytest.mark.parametrize(
    "entrada",
    ["¿¿ dónde  ?? crece", "! ! ¡ ¡hola", "a ,, b ;; c", "🌿 ¿ x ? 🌿", "...... ."],
)
def test_limpiar_dos_veces_no_cambia_nada(entrada):
    # RR_17: al elegir una especie, el frontend reenvía el texto ya limpio.
    una_vez = limpiar_consulta(entrada)
    assert limpiar_consulta(una_vez) == una_vez


# --- RR_21 criterio 3: el texto queda listo para procesarse ----------------------


def test_la_consulta_llega_limpia_al_procesamiento():
    consulta = ConsultaRequest(texto="  <b>¿¿Dónde</b>   crece el pejibaye??  🌴 ")
    assert consulta.texto == "¿Dónde crece el pejibaye?"


@pytest.mark.parametrize("texto", ["🌿🌸", "   ", "★ ★ ★", "<b></b> 👍"])
def test_una_consulta_sin_nada_que_procesar_se_rechaza_como_vacia(texto):
    with pytest.raises(ValidationError, match="La consulta no puede estar vacía"):
        ConsultaRequest(texto=texto)


def test_una_consulta_vacia_se_rechaza_en_espanol():
    with pytest.raises(ValidationError, match="La consulta no puede estar vacía"):
        ConsultaRequest(texto="")


# --- RR_34: límite máximo de longitud --------------------------------------------


def test_el_limite_esta_definido():
    # Criterio 3.
    assert config.LONGITUD_MAXIMA_CONSULTA == 500


def test_una_consulta_en_el_limite_se_acepta():
    texto = "a" * config.LONGITUD_MAXIMA_CONSULTA
    assert ConsultaRequest(texto=texto).texto == texto


def test_una_consulta_que_supera_el_limite_se_rechaza_con_el_motivo():
    # Criterios 1 y 2: se rechaza y el mensaje dice cuánto tiene y cuál es el máximo.
    largo = config.LONGITUD_MAXIMA_CONSULTA + 1
    with pytest.raises(ValidationError, match=f"tiene {largo} caracteres y el máximo es 500"):
        ConsultaRequest(texto="a" * largo)


def test_el_limite_se_mide_sobre_lo_que_escribio_el_usuario():
    # Igual que el contador del frontend: los espacios también cuentan.
    with pytest.raises(ValidationError):
        ConsultaRequest(texto="cedro" + " " * config.LONGITUD_MAXIMA_CONSULTA)


def test_la_api_rechaza_la_consulta_larga_con_el_mensaje_en_espanol(visitante):
    largo = config.LONGITUD_MAXIMA_CONSULTA + 20
    salida = api.post("/consultas", json={"texto": "a" * largo}, headers=visitante)
    assert salida.status_code == 422
    mensaje = salida.json()["detail"][0]["msg"]
    assert f"La consulta tiene {largo} caracteres" in mensaje


def test_la_sesion_informa_el_limite(visitante):
    # Criterio 3: el frontend usa este valor en lugar de escribirlo a mano.
    sesion = api.get("/auth/sesion", headers=visitante).json()
    assert sesion["longitud_maxima_consulta"] == config.LONGITUD_MAXIMA_CONSULTA


# --- RR_35: acentos y mayúsculas no cambian la búsqueda ---------------------------


def _ids(texto: str) -> set[str]:
    return {e.id for e in catalogo.buscar_especies(texto)}


@pytest.mark.parametrize(
    "variante",
    [
        "¿Dónde crece el PEJIBAYE?",
        "¿donde crece el pejíbaye?",
        "¿DÓNDE CRECE EL PEJÍBAYE?",
        "¿Dónde crece el Pejibaye?",
    ],
)
def test_tildes_y_mayusculas_no_cambian_las_especies_encontradas(variante):
    # Criterios 1 y 2.
    assert _ids(variante) == _ids("¿Dónde crece el pejibaye?") == {"bactris-gasipaes"}


def test_el_nombre_cientifico_se_encuentra_con_cualquier_forma():
    assert _ids("CEDRELA ODORATA") == _ids("cédrela odoráta") == {"cedrela-odorata"}


@pytest.mark.parametrize(
    "variante",
    ["¿Dónde crece Quercus costaricensis?", "¿DONDE CRECE quercus costaricensis?"],
)
def test_tildes_y_mayusculas_no_cambian_el_tipo_de_pregunta(variante):
    especie = "Quercus costaricensis"
    esperado = analizar("¿dónde crece Quercus costaricensis?", especie).tipo
    assert analizar(variante, especie).tipo == esperado


def test_la_normalizacion_es_para_comparar():
    # Criterio 3: se aplica antes de buscar (en el catálogo), sobre una copia.
    assert normalizar("Guaría MORADA") == "guaria morada"
    consulta = ConsultaRequest(texto="Guaría MORADA")
    assert consulta.texto == "Guaría MORADA"


# --- RR_35 criterio 3: la pregunta que recibe CR-BioLM ------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("¿Dónde crece QUERCUS COSTARICENSIS?", "¿Dónde crece Quercus costaricensis?"),
        (
            "¿dónde crece quércus costaricénsis en Talamanca?",
            "¿dónde crece Quercus costaricensis en Talamanca?",
        ),
        ("¿Dónde crece Quercus costaricensis?", "¿Dónde crece Quercus costaricensis?"),
        ("¿Dónde crece el roble negro?", "¿Dónde crece el roble negro?"),  # no aparece: igual
        ("Quercus", "Quercus"),  # el género solo no es el nombre
    ],
)
def test_cr_biolm_recibe_el_nombre_como_en_el_catalogo(texto, esperado):
    # CR-BioLM reconoce la especie solo si está escrita como en el catálogo.
    assert con_nombre_canonico(texto, "Quercus costaricensis") == esperado


def test_el_nombre_con_rango_infraespecifico_tambien_se_corrige():
    texto = "Ficha de INGA EDULIS VAR. MINUTULA, por favor"
    esperado = "Ficha de Inga edulis var. minutula, por favor"
    assert con_nombre_canonico(texto, "Inga edulis var. minutula") == esperado
