"""Pruebas de RR_23 — corrección de errores ortográficos (services/correccion.py).

No necesitan CR-BioLM ni la BD: se corrige contra una lista de nombres fija. Las
que pasan por el catálogo de CR-BioLM están en test_catalogo_crbiolm.py.
"""

import pytest

from app import config
from app.sanitizacion import normalizar
from app.services.correccion import corregir_nombres, letras_distintas

NOMBRES = {
    normalizar(n): n
    for n in ["Quercus costaricensis", "Quercus oleoides", "Quercus alba", "Quercus alta"]
}


@pytest.mark.parametrize(
    ("a", "b", "letras"),
    [
        ("quercus", "quercus", 0),
        ("querus", "quercus", 1),  # falta una
        ("costaricencis", "costaricensis", 1),  # una cambiada
        ("quercuss", "quercus", 1),  # sobra una
        ("ab", "ba", 2),
        ("", "abc", 3),
    ],
)
def test_letras_distintas(a, b, letras):
    assert letras_distintas(a, b) == letras


# --- criterio 1: variaciones simples, hasta dos letras --------------------------------


@pytest.mark.parametrize(
    "escrito",
    ["Querus costaricensis", "Quercus costaricencis", "Qercus costarisensis"],
)
def test_corrige_hasta_dos_letras_mal_escritas(escrito):
    assert corregir_nombres(escrito, NOMBRES) == "Quercus costaricensis"


def test_con_tres_letras_mal_no_se_corrige():
    assert corregir_nombres("Qercus kostarisensis", NOMBRES) == "Qercus kostarisensis"


def test_ante_un_empate_no_se_adivina():
    # "alza" está a una letra de "alba" y de "alta".
    assert corregir_nombres("Quercus alza", NOMBRES) == "Quercus alza"


def test_tildes_y_mayusculas_no_impiden_corregir():
    assert corregir_nombres("QUERUS costaricénsis", NOMBRES) == "Quercus costaricensis"


def test_el_maximo_de_letras_se_configura(monkeypatch):
    monkeypatch.setattr(config, "LETRAS_MAXIMAS_CORRECCION", 1)
    assert corregir_nombres("Qercus costarisensis", NOMBRES) == "Qercus costarisensis"


# --- criterio 2: no altera el sentido de la consulta ----------------------------------


def test_solo_cambia_el_nombre_y_el_resto_queda_igual():
    texto = "¿Dónde crece  Querus costaricensis en Talamanca?"
    assert corregir_nombres(texto, NOMBRES) == "¿Dónde crece  Quercus costaricensis en Talamanca?"


@pytest.mark.parametrize(
    "texto",
    [
        "¿Dónde crece Quercus costaricensis?",  # ya está bien escrito
        "¿Dónde crece el roble negro?",  # sin nombre científico
        "asdfgh",
        "",
    ],
)
def test_lo_que_no_es_un_nombre_mal_escrito_no_cambia(texto):
    assert corregir_nombres(texto, NOMBRES) == texto


def test_sin_catalogo_no_se_corrige_nada():
    assert corregir_nombres("Querus costaricensis", {}) == "Querus costaricensis"
