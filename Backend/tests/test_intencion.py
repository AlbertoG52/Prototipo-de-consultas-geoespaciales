"""Pruebas de RR_41 criterio 1 (services/intencion.py). No usan la BD."""

import pytest

from app.services import intencion
from app.services.intencion import TipoPregunta, analizar, palabras

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


@pytest.mark.parametrize(
    ("texto", "tipo"),
    [
        ("¿Dónde crece Quercus costaricensis?", TipoPregunta.DISTRIBUCION),
        ("¿Cómo son las hojas de Quercus costaricensis?", TipoPregunta.DESCRIPCION),
        ("Quercus costaricensis", TipoPregunta.GENERAL),
        # geográfica y descriptiva: gana la geográfica
        ("¿Cómo son las hojas de Quercus costaricensis y dónde crece?", TipoPregunta.DISTRIBUCION),
    ],
)
def test_tipo_de_pregunta(texto, tipo):
    assert analizar(texto, ESPECIE).tipo == tipo


def test_las_palabras_de_habitat_dan_el_tipo_habitat(monkeypatch):
    # RR_29: la lista HABITAT la llena Cristopher; una pregunta de hábitat sigue
    # siendo geoespacial (trae GBIF y mapa).
    habitat = frozenset({"ambiente"})
    monkeypatch.setattr(intencion, "HABITAT", habitat)
    monkeypatch.setattr(
        intencion,
        "_PRIORIDAD",
        (
            (TipoPregunta.DISTRIBUCION, intencion.GEOESPACIALES),
            (TipoPregunta.HABITAT, habitat),
            (TipoPregunta.DESCRIPCION, intencion.DESCRIPTIVAS),
        ),
    )
    resultado = analizar("¿En qué ambiente vive Quercus costaricensis?", ESPECIE)
    assert resultado.tipo == TipoPregunta.HABITAT
    assert resultado.geoespacial
