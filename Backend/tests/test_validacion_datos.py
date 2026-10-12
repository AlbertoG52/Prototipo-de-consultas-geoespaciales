"""Pruebas de las reglas de RR_60 y RR_43 (services/validacion_datos.py). No usan la BD."""

import pytest

from app import config
from app.services.validacion_datos import alcanza_para_mapa, misma_especie, punto_valido


@pytest.mark.parametrize(
    "recibida", ["Quercus costaricensis", "quercus costaricensis", "  Quercus   costaricensis "]
)
def test_misma_especie_tolera_mayusculas_y_espacios(recibida):
    assert misma_especie("Quercus costaricensis", recibida)


@pytest.mark.parametrize(
    "recibida",
    [
        "Quercus oleoides",  # otro epíteto
        "Quercus",  # otro rango
        "Quercus costaricensis var. x",  # otra variedad
        "",
        None,
        123,
    ],
)
def test_otra_especie_no_corresponde(recibida):
    assert not misma_especie("Quercus costaricensis", recibida)


def test_un_punto_en_costa_rica_es_valido():
    assert punto_valido({"lat": 9.93, "lon": -84.08})


@pytest.mark.parametrize(
    "punto",
    [
        {"lat": 0, "lon": 0},
        {"lat": 8.9, "lon": -79.5},  # Panamá
        {"lat": 5.53, "lon": -87.05},  # isla del Coco: fuera de la caja de CR-BioLM
        {"lat": None, "lon": -84.0},
        {"lat": "9.9", "lon": -84.0},
        {"lat": float("nan"), "lon": -84.0},
        {"lat": True, "lon": -84.0},
        {"lon": -84.0},
        "9.9,-84.0",
    ],
)
def test_puntos_invalidos(punto):
    assert not punto_valido(punto)


def test_minimo_para_el_mapa(monkeypatch):
    monkeypatch.setattr(config, "MINIMO_REGISTROS_MAPA", 5)
    assert not alcanza_para_mapa(4)
    assert alcanza_para_mapa(5)
