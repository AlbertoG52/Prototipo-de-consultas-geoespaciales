"""Pruebas de RR_20 (ficha completa) y RR_16 (sugerencias de nombres).

No necesitan base de datos: el catálogo es provisional y vive en memoria, y la
coincidencia de RR_16 se prueba sobre listas de especies. Se ejecutan con:
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


def test_especie_sin_datos_geoespaciales_no_trae_registros():
    # RR_06 criterio 5: sin registros el frontend omite el mapa.
    respuesta = catalogo.construir_respuesta("hylocereus-costaricensis", "")
    assert respuesta.registros == []
    assert respuesta.total_registros == 0
    assert respuesta.texto


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


# --- RR_16: sugerencias de nombres -----------------------------------------

def _guardadas():
    """Especies como quedan en consultas.respuesta, con una repetida."""
    ids = ["guarianthe-skinneri", "guarianthe-aurantiaca", "cedrela-odorata", "guarianthe-skinneri"]
    return [catalogo.construir_respuesta(i, "").especie.model_dump() for i in ids]


def _ids(fragmento: str) -> list[str]:
    return [c.id for c in especies.coincidencias(_guardadas(), fragmento)]


def test_sugiere_por_nombre_comun_sin_tildes_y_sin_repetir():
    assert _ids("guaría") == ["guarianthe-skinneri", "guarianthe-aurantiaca"]


def test_sugiere_por_nombre_cientifico_y_por_cualquier_palabra():
    assert _ids("Cedrela") == ["cedrela-odorata"]
    assert _ids("odor") == ["cedrela-odorata"]
    assert _ids("mora") == ["guarianthe-skinneri"]


def test_sin_coincidencias_no_sugiere_nada():
    assert _ids("roble") == []


def test_respeta_el_limite_de_sugerencias():
    muchas = [
        {"id": f"sp-{i}", "nombre_comun": f"Planta {i}", "nombre_cientifico": f"Genus sp{i}", "familia": "X"}
        for i in range(10)
    ]
    assert len(especies.coincidencias(muchas, "planta")) == especies.LIMITE_SUGERENCIAS


def test_sugerencias_sin_sesion_valida_responde_401():
    sin_sesion = Identidad(tipo=TIPO_ANONIMO, sesion_id="", anon_id=None, token_invalido=True)
    with pytest.raises(HTTPException) as error:
        especies.sugerir_especies("guaria", sin_sesion, db=None)
    assert error.value.status_code == 401
