"""Pruebas de RR_57 — registro del tiempo de respuesta (services/tiempos.py).

Usan el catálogo de demostración y la BD. Se ejecutan con:
    docker compose exec backend python -m pytest tests/test_tiempos_respuesta.py -q
"""

import logging
import time

import pytest

from app import config
from app.main import app
from app.routers import admin
from app.services import tiempos
from app.services.catalogo import CatalogoDemo, obtener_catalogo

from apoyo import api, crear_cuenta_verificada, sql

PEJIBAYE = "pejibaye"  # el catálogo de demostración lo resuelve con una sola especie
PASSWORD = "ClaveSegura123"


class CatalogoLento(CatalogoDemo):
    def __init__(self, segundos: float):
        self.segundos = segundos

    def construir_respuesta(self, especie_id, texto_consulta):
        time.sleep(self.segundos)
        return super().construir_respuesta(especie_id, texto_consulta)


class CatalogoRoto(CatalogoDemo):
    def construir_respuesta(self, especie_id, texto_consulta):
        raise RuntimeError("falla inesperada")


@pytest.fixture
def nuevos_tiempos():
    """Devuelve las filas de tiempos_respuesta creadas durante la prueba y las borra al final."""
    desde = sql("SELECT coalesce(max(id), 0) FROM tiempos_respuesta").scalar()

    def leer() -> list[dict]:
        filas = sql("SELECT * FROM tiempos_respuesta WHERE id > :d ORDER BY id", d=desde)
        return [dict(f._mapping) for f in filas]

    yield leer
    sql("DELETE FROM tiempos_respuesta WHERE id > :d", d=desde)


@pytest.fixture
def visitante():
    token = api.post("/auth/anonimo").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cuenta(correos_de_prueba):
    correo = correos_de_prueba("tiempos")
    crear_cuenta_verificada(correo, PASSWORD)
    token = api.post("/auth/login", json={"correo": correo, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


@pytest.fixture
def con_catalogo():
    def usar(catalogo):
        app.dependency_overrides[obtener_catalogo] = lambda: catalogo

    yield usar
    app.dependency_overrides.pop(obtener_catalogo, None)


@pytest.fixture
def como_supermoderador():
    """Salta la verificación de rol del router /admin (la prueba test_roles.py la cubre)."""
    [verificar_rol] = [d.dependency for d in admin.router.dependencies]
    app.dependency_overrides[verificar_rol] = lambda: None
    yield
    app.dependency_overrides.pop(verificar_rol, None)


def _consultar(cabeceras, texto=PEJIBAYE):
    return api.post("/consultas", headers=cabeceras, json={"texto": texto})


# --- criterio 1: se registra cada consulta ------------------------------------------


def test_una_consulta_resuelta_queda_registrada(visitante, nuevos_tiempos):
    assert _consultar(visitante).status_code == 200
    [fila] = nuevos_tiempos()
    assert fila["resultado"] == "resuelta"
    assert fila["tipo_sesion"] == "anonimo"
    assert fila["especie_id"] == "bactris-gasipaes"
    assert fila["consulta_id"] is None  # del visitante no se guarda la consulta
    assert fila["duracion_ms"] >= 0


def test_mide_el_tiempo_real_de_la_consulta(visitante, nuevos_tiempos, con_catalogo):
    con_catalogo(CatalogoLento(0.3))
    _consultar(visitante)
    [fila] = nuevos_tiempos()
    assert fila["duracion_ms"] >= 300


def test_de_una_cuenta_se_enlaza_la_consulta(cuenta, nuevos_tiempos):
    consulta = _consultar(cuenta).json()
    [fila] = nuevos_tiempos()
    assert fila["tipo_sesion"] == "usuario"
    assert fila["consulta_id"] == consulta["id"]


def test_tambien_se_registran_las_que_no_se_resuelven(visitante, nuevos_tiempos):
    _consultar(visitante, "una consulta sin ninguna planta")
    [fila] = nuevos_tiempos()
    assert fila["resultado"] == "sin_coincidencias" and fila["especie_id"] is None


def test_se_registra_la_consulta_cortada_por_tiempo(
    visitante, nuevos_tiempos, con_catalogo, monkeypatch
):
    monkeypatch.setattr(config, "SEGUNDOS_MAXIMOS_CONSULTA", 0.2)
    con_catalogo(CatalogoLento(0.4))
    assert _consultar(visitante).status_code == 504
    [fila] = nuevos_tiempos()
    assert fila["resultado"] == "tiempo_agotado"


def test_se_registra_la_consulta_que_falla(visitante, nuevos_tiempos, con_catalogo):
    con_catalogo(CatalogoRoto())
    with pytest.raises(RuntimeError):
        _consultar(visitante)
    [fila] = nuevos_tiempos()
    assert fila["resultado"] == "error"


def test_si_no_se_puede_guardar_la_consulta_responde_igual(visitante, monkeypatch, caplog):
    def sin_bd():
        raise ConnectionError("BD caída")

    monkeypatch.setattr(tiempos, "SessionLocal", sin_bd)
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        assert _consultar(visitante).status_code == 200
    assert "no se pudo guardar el tiempo de respuesta" in caplog.text


# --- criterio 3: identificar las lentas ------------------------------------------------


def test_una_consulta_lenta_queda_en_el_log(
    visitante, nuevos_tiempos, con_catalogo, monkeypatch, caplog
):
    monkeypatch.setattr(config, "SEGUNDOS_RESPUESTA_LENTA", 0.1)
    con_catalogo(CatalogoLento(0.2))
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        _consultar(visitante)
    assert "RR_57: consulta lenta" in caplog.text


# --- criterio 2: disponible para el equipo técnico ---------------------------------------


def test_el_resumen_separa_las_lentas(
    visitante, nuevos_tiempos, con_catalogo, como_supermoderador, monkeypatch
):
    monkeypatch.setattr(config, "SEGUNDOS_RESPUESTA_LENTA", 0.25)
    _consultar(visitante)  # rápida
    con_catalogo(CatalogoLento(0.3))
    _consultar(visitante)  # lenta
    rapida, lenta = nuevos_tiempos()

    datos = api.get("/admin/tiempos", params={"limite": 500}).json()
    assert datos["umbral_lenta_ms"] == 250
    por_id = {r["id"]: r for r in datos["registros"]}
    assert por_id[rapida["id"]]["lenta"] is False
    assert por_id[lenta["id"]]["lenta"] is True
    assert datos["total"] >= 2 and datos["lentas"] >= 1
    assert datos["maximo_ms"] >= lenta["duracion_ms"]

    solo_lentas = api.get("/admin/tiempos", params={"solo_lentas": True}).json()
    ids = {r["id"] for r in solo_lentas["registros"]}
    assert lenta["id"] in ids and rapida["id"] not in ids
    assert all(r["lenta"] for r in solo_lentas["registros"])


def test_el_endpoint_es_solo_del_supermoderador(visitante):
    assert api.get("/admin/tiempos", headers=visitante).status_code in (401, 403)
