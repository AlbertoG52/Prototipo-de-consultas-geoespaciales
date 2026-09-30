"""Pruebas de RR_20 — ficha completa de la especie.

No necesitan base de datos: el catálogo es provisional y vive en memoria. Se
ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
import pytest
from fastapi import HTTPException

from app.routers import especies
from app.security import TIPO_ANONIMO, Identidad
from app.services import catalogo

# Un visitante con sesión anónima válida puede ver la ficha (RR_00_11).
_VISITANTE = Identidad(tipo=TIPO_ANONIMO, sesion_id="anon-1", anon_id="anon-1")


def _ficha(especie: str):
    return especies.ficha_de_especie(especie, _VISITANTE)


# --- criterio 1: la ficha trae nombre, familia, hábitat y elevación --------

def test_la_ficha_trae_los_datos_de_la_especie():
    ficha = _ficha("cedrela-odorata")
    assert ficha.nombre_comun == "Cedro amargo"
    assert ficha.nombre_cientifico == "Cedrela odorata"
    assert ficha.familia == "Meliaceae"
    assert ficha.habitat and ficha.elevacion
    assert ficha.total_registros == len(ficha.registros) > 0


# --- criterio 2: corresponde a la especie consultada ----------------------

@pytest.mark.parametrize(
    "especie_id",
    [
        "guarianthe-skinneri",
        "guarianthe-aurantiaca",
        "cedrela-odorata",
        "cedrela-tonduzii",
        "quercus-costaricensis",
        "bactris-gasipaes",
    ],
)
def test_cada_especie_tiene_su_propia_ficha(especie_id):
    ficha = _ficha(especie_id)
    assert ficha.id == especie_id
    # Los datos coinciden con los de la respuesta del agente para esa especie.
    respuesta = catalogo.construir_respuesta(especie_id, "")
    assert ficha.nombre_cientifico == respuesta.especie.nombre_cientifico
    assert ficha.elevacion == respuesta.elevacion
    assert ficha.registros == respuesta.registros


def test_ya_no_es_siempre_la_guaria_morada():
    assert _ficha("bactris-gasipaes").nombre_comun == "Pejibaye"


def test_acepta_el_nombre_cientifico():
    # Los enlaces anteriores usaban el nombre científico.
    assert _ficha("Guarianthe skinneri").id == "guarianthe-skinneri"


def test_especie_inexistente_responde_404():
    with pytest.raises(HTTPException) as error:
        _ficha("no-existe")
    assert error.value.status_code == 404


def test_sin_sesion_valida_responde_401():
    # RR_00_10: la validación se hace en el servidor.
    sin_sesion = Identidad(tipo=TIPO_ANONIMO, sesion_id="", anon_id=None, token_invalido=True)
    with pytest.raises(HTTPException) as error:
        especies.ficha_de_especie("cedrela-odorata", sin_sesion)
    assert error.value.status_code == 401
