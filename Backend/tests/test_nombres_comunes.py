"""Pruebas de services/nombres_comunes.py — RR_25.

Qué frases de la consulta se le preguntan a CR-BioLM como posibles nombres
comunes. Que el catálogo las resuelve está en test_catalogo_crbiolm.py.
"""

import pytest

from app import config
from app.services.nombres_comunes import Frase, en_singular, frases_candidatas


def _textos(texto: str) -> list[str]:
    return [f.texto for f in frases_candidatas(texto)]


def test_las_frases_van_de_la_mas_larga_a_la_mas_corta():
    assert _textos("¿Dónde crece el roble negro?") == ["roble negro", "roble", "negro"]


def test_una_frase_no_empieza_ni_termina_con_palabras_de_la_pregunta():
    textos = _textos("¿Dónde crece la guaria morada en Costa Rica?")
    assert textos[0] == "guaria morada"
    assert not any(t.split()[0].lower() in {"dónde", "crece", "la", "en"} for t in textos)
    assert "Costa Rica" not in textos


def test_una_frase_puede_tener_palabras_cortas_en_medio():
    assert _textos("¿Dónde crece la olla de mono?")[0] == "olla de mono"


def test_conserva_lo_que_escribio_y_su_posicion():
    """CR-BioLM compara primero con tildes ("poró" no es "poro")."""
    texto = "¿Dónde crece el Poró?"
    [frase] = frases_candidatas(texto)
    assert frase.texto == "Poró"
    assert texto[frase.inicio : frase.fin] == "Poró"


def test_cuantas_frases_se_prueban_se_configura(monkeypatch):
    monkeypatch.setattr(config, "NOMBRES_COMUNES_FRASES_MAXIMAS", 2)
    assert _textos("¿Dónde crece el roble negro?") == ["roble negro", "roble"]


def test_sin_palabras_no_hay_frases():
    assert frases_candidatas("¿? 123") == []


@pytest.mark.parametrize(
    ("nombre", "singular"),
    [
        ("ceibas", "ceiba"),
        ("ollas de monos", "olla de mono"),  # "de" no se toca
        ("datos", None),  # palabras de la pregunta no cambian
        ("ceiba", None),
        ("mas", None),  # palabras de tres letras no cambian
    ],
)
def test_en_singular(nombre, singular):
    assert en_singular(nombre) == singular


def test_dos_frases_se_cruzan_si_comparten_una_parte():
    roble_negro = Frase("roble negro", 16, 27)
    assert roble_negro.se_cruza_con(Frase("negro", 22, 27))
    assert not roble_negro.se_cruza_con(Frase("Talamanca", 31, 40))
