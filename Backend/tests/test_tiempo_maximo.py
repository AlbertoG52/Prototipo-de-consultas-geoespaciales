"""Pruebas de RR_38 — tiempo máximo de procesamiento de una consulta.

Usan un catálogo falso y lento en lugar del de demostración, y un tiempo
máximo de fracciones de segundo. Las que pasan por la API necesitan la BD.
Se ejecutan con:
    docker compose exec backend python -m pytest tests/test_tiempo_maximo.py -q
"""

import time

import pytest

from app import config
from app.errores import TiempoAgotado
from app.main import app
from app.services.catalogo import CatalogoDemo, obtener_catalogo
from app.services.mcp_cliente import MCPTiempoAgotado
from app.tiempo import plazo, segundos_restantes, verificar_plazo

from apoyo import api

PEJIBAYE = "pejibaye"  # el catálogo de demostración lo resuelve con una sola especie


class CatalogoLento(CatalogoDemo):
    """Igual al de demostración, pero tarda en armar la respuesta."""

    def __init__(self, segundos: float):
        self.segundos = segundos

    def construir_respuesta(self, especie_id, texto_consulta):
        time.sleep(self.segundos)
        return super().construir_respuesta(especie_id, texto_consulta)


class CatalogoSinRespuestaDeCRBioLM(CatalogoDemo):
    """Simula que la llamada a CR-BioLM se cortó por tiempo."""

    def construir_respuesta(self, especie_id, texto_consulta):
        raise MCPTiempoAgotado("get_species", "superó 0.2 s sin responder")


@pytest.fixture
def visitante():
    token = api.post("/auth/anonimo").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def con_catalogo():
    """Cambia el catálogo de la API durante una prueba."""

    def usar(catalogo):
        app.dependency_overrides[obtener_catalogo] = lambda: catalogo

    yield usar
    app.dependency_overrides.pop(obtener_catalogo, None)


def _consultar(cabeceras, texto=PEJIBAYE):
    return api.post("/consultas", headers=cabeceras, json={"texto": texto})


def _restantes(cabeceras) -> int:
    return api.get("/auth/sesion", headers=cabeceras).json()["consultas_restantes"]


# --- el plazo -----------------------------------------------------------------


def test_sin_plazo_no_hay_limite():
    assert segundos_restantes() is None
    verificar_plazo()  # no lanza


def test_el_plazo_vence_y_se_cierra_al_salir():
    with plazo(0.05):
        assert 0 < segundos_restantes() <= 0.05
        time.sleep(0.06)
        with pytest.raises(TiempoAgotado) as error:
            verificar_plazo()
    assert error.value.estado_http == 504
    assert segundos_restantes() is None


# --- criterio 3: el tiempo máximo está definido -------------------------------


def test_el_tiempo_maximo_esta_definido_y_se_informa(visitante):
    assert config.SEGUNDOS_MAXIMOS_CONSULTA > config.MCP_TIMEOUT_SEGUNDOS
    sesion = api.get("/auth/sesion", headers=visitante).json()
    assert sesion["segundos_maximos_consulta"] == config.SEGUNDOS_MAXIMOS_CONSULTA


# --- criterio 1: mensaje de error al superarlo ----------------------------------


def test_consulta_lenta_se_cancela_con_mensaje(visitante, con_catalogo, monkeypatch):
    monkeypatch.setattr(config, "SEGUNDOS_MAXIMOS_CONSULTA", 0.2)
    con_catalogo(CatalogoLento(0.3))

    respuesta = _consultar(visitante)

    assert respuesta.status_code == 504
    detalle = respuesta.json()["detail"]
    assert "tiempo máximo de 0.2 segundos" in detalle
    assert "reintentar" in detalle


def test_si_cr_biolm_no_responde_a_tiempo_es_el_mismo_error(visitante, con_catalogo):
    con_catalogo(CatalogoSinRespuestaDeCRBioLM())

    respuesta = _consultar(visitante)

    assert respuesta.status_code == 504
    assert "tiempo máximo" in respuesta.json()["detail"]


# --- criterio 2: se puede reintentar, y el intento fallido no cuesta -----------


def test_la_consulta_cancelada_no_se_cobra_y_se_puede_reintentar(
    visitante, con_catalogo, monkeypatch
):
    antes = _restantes(visitante)
    monkeypatch.setattr(config, "SEGUNDOS_MAXIMOS_CONSULTA", 0.2)
    con_catalogo(CatalogoLento(0.3))
    assert _consultar(visitante).status_code == 504
    assert _restantes(visitante) == antes

    # Reintento cuando el servicio vuelve a responder a tiempo.
    con_catalogo(CatalogoLento(0))
    reintento = _consultar(visitante)
    assert reintento.status_code == 200
    assert reintento.json()["estado"] == "resuelta"
    assert _restantes(visitante) == antes - 1


def test_la_consulta_cancelada_de_una_cuenta_no_se_guarda(
    correos_de_prueba, con_catalogo, monkeypatch
):
    from apoyo import crear_cuenta_verificada

    correo = correos_de_prueba()
    crear_cuenta_verificada(correo, "Correcta#2024")
    token = api.post("/auth/login", json={"correo": correo, "password": "Correcta#2024"})
    cabeceras = {"Authorization": f"Bearer {token.json()['access_token']}"}
    monkeypatch.setattr(config, "SEGUNDOS_MAXIMOS_CONSULTA", 0.2)
    con_catalogo(CatalogoLento(0.3))

    assert _consultar(cabeceras).status_code == 504
    assert api.get("/conversaciones", headers=cabeceras).json() == []
