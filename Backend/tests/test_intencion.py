"""Pruebas de RR_41 criterio 1 (services/intencion.py). No usan la BD."""

import pytest

from app.services.intencion import analizar, palabras

ESPECIE = "Quercus costaricensis"


@pytest.mark.parametrize(
    "texto",
    [
        "¿Dónde crece Quercus costaricensis?",
        "DONDE CRECE quercus costaricensis",
        "¿A qué altitud vive Quercus costaricensis?",
        "Quercus costaricensis en Guanacaste",
        "Mapa de Quercus costaricensis",
        "¿Cuál es la distribución de Quercus costaricensis?",
        # pregunta descriptiva Y geográfica: se responde con todo
        "¿Cómo son las hojas de Quercus costaricensis y dónde crece?",
    ],
)
def test_consultas_geoespaciales(texto):
    assert analizar(texto, ESPECIE).geoespacial


@pytest.mark.parametrize(
    "texto",
    [
        "¿Cómo son las hojas de Quercus costaricensis?",
        "¿De qué color son las flores de Quercus costaricensis?",
        "¿De qué familia es Quercus costaricensis?",
        "Morfología de Quercus costaricensis",
    ],
)
def test_consultas_descriptivas_no_piden_gbif_ni_mapa(texto):
    intencion = analizar(texto, ESPECIE)
    assert not intencion.geoespacial
    assert intencion.pregunta_especifica


@pytest.mark.parametrize(
    "texto",
    ["Quercus costaricensis", "quercus costaricensis", "Información sobre Quercus costaricensis"],
)
def test_solo_el_nombre_es_geoespacial_y_sin_pregunta_concreta(texto):
    intencion = analizar(texto, ESPECIE)
    assert intencion.geoespacial  # el caso principal: se responde con todo
    assert not intencion.pregunta_especifica


def test_sin_texto_se_pide_todo():
    intencion = analizar("", ESPECIE)
    assert intencion.geoespacial and not intencion.pregunta_especifica


def test_palabras_sin_tildes_ni_signos():
    assert palabras("¿Dónde CRECE el árbol?") == ["donde", "crece", "el", "arbol"]
