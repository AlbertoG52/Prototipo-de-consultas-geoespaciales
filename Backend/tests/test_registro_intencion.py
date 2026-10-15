"""Pruebas de RR_33 — registro interno de la intención detectada (y RR_29
criterio 3: el tipo de consulta queda registrado).

Pasan por la API con el catálogo de demostración y usan la BD: leen las filas de
tiempos_respuesta (tablas 015 y 017) que crea cada prueba y las borran al final.
Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import time

import pytest

from app import config
from app.db import SessionLocal
from app.dominio import IntencionConsulta, MotivoOrientacion, TipoPregunta
from app.main import app
from app.services import tiempos
from app.services.catalogo import CatalogoDemo, obtener_catalogo

from apoyo import api, crear_cuenta_verificada, sql

PASSWORD = "ClaveSegura123"


class CatalogoLento(CatalogoDemo):
    """Tarda más que el tiempo máximo de la consulta (RR_38)."""

    def construir_respuesta(self, especie_id, texto_consulta):
        time.sleep(0.4)
        return super().construir_respuesta(especie_id, texto_consulta)


@pytest.fixture
def visitante():
    token = api.post("/auth/anonimo").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def nuevas_filas():
    """Las filas de tiempos_respuesta creadas durante la prueba; al final se borran."""
    desde = sql("SELECT coalesce(max(id), 0) FROM tiempos_respuesta").scalar()

    def leer() -> list[dict]:
        filas = sql("SELECT * FROM tiempos_respuesta WHERE id > :d ORDER BY id", d=desde)
        return [dict(f._mapping) for f in filas]

    yield leer
    sql("DELETE FROM tiempos_respuesta WHERE id > :d", d=desde)


def _consultar(cabeceras, texto):
    return api.post("/consultas", headers=cabeceras, json={"texto": texto})


def test_los_valores_de_intencion_son_los_tipos_y_los_motivos():
    assert {i.value for i in IntencionConsulta} == {t.value for t in TipoPregunta} | {
        m.value for m in MotivoOrientacion
    }


# --- criterio 1: se registra la intención de cada consulta --------------------------


@pytest.mark.parametrize(
    ("texto", "intencion", "resultado"),
    [
        ("¿Dónde crece el pejibaye?", "distribucion", "resuelta"),
        ("¿En qué tipo de bosque vive el pejibaye?", "habitat", "resuelta"),  # RR_29
        ("¿Cómo son las hojas del pejibaye?", "descripcion", "resuelta"),
        ("pejibaye", "general", "resuelta"),
        ("¿Dónde crece la guaria?", "distribucion", "ambigua"),
        ("planta inventada xyz", "general", "sin_coincidencias"),
        ("hola", "saludo", "orientacion"),
        ("¿Qué puedo preguntar?", "ayuda", "orientacion"),
        ("Where does Quercus costaricensis grow?", "idioma", "orientacion"),
        ("asdfgh", "sin_sentido", "orientacion"),
        # Solo se sabe después de buscar: la intención del texto se corrige al terminar.
        ("¿Quién ganó el mundial?", "fuera_de_tema", "orientacion"),
    ],
)
def test_cada_consulta_registra_su_intencion(visitante, nuevas_filas, texto, intencion, resultado):
    _consultar(visitante, texto)
    [fila] = nuevas_filas()
    assert (fila["intencion"], fila["resultado"]) == (intencion, resultado)


def test_se_registra_aunque_la_consulta_se_corte_por_tiempo(visitante, nuevas_filas, monkeypatch):
    monkeypatch.setattr(config, "SEGUNDOS_MAXIMOS_CONSULTA", 0.2)
    app.dependency_overrides[obtener_catalogo] = CatalogoLento
    try:
        assert _consultar(visitante, "¿Dónde crece el pejibaye?").status_code == 504
    finally:
        app.dependency_overrides.pop(obtener_catalogo, None)
    [fila] = nuevas_filas()
    assert (fila["intencion"], fila["resultado"]) == ("distribucion", "tiempo_agotado")


def test_del_visitante_no_se_guarda_el_texto(visitante, nuevas_filas):
    # RR_00_11: queda qué intentó hacer, no qué escribió.
    _consultar(visitante, "¿Dónde crece el pejibaye?")
    [fila] = nuevas_filas()
    assert "texto" not in fila
    assert fila["tipo_sesion"] == "anonimo" and fila["consulta_id"] is None


# --- criterio 2: asociado a un identificador único de consulta ----------------------


def test_cada_registro_tiene_su_identificador_y_el_de_la_consulta(correos_de_prueba, nuevas_filas):
    correo = correos_de_prueba("intencion")
    crear_cuenta_verificada(correo, PASSWORD)
    token = api.post("/auth/login", json={"correo": correo, "password": PASSWORD}).json()
    cuenta = {"Authorization": f"Bearer {token['access_token']}"}

    primera = _consultar(cuenta, "¿Dónde crece el pejibaye?").json()
    segunda = _consultar(cuenta, "hola").json()

    filas = nuevas_filas()
    assert len({f["id"] for f in filas}) == 2  # un id único por consulta
    assert [(f["consulta_id"], f["intencion"]) for f in filas] == [
        (primera["id"], "distribucion"),
        (segunda["id"], "saludo"),
    ]


# --- criterio 3: disponible para monitoreo ------------------------------------------


def _conteo(intencion: str) -> int:
    with SessionLocal() as db:
        resumen = tiempos.resumen(db, dias=1, solo_lentas=False, limite=5)
    return next((c.total for c in resumen.por_intencion if c.intencion == intencion), 0)


def test_el_resumen_cuenta_las_consultas_de_cada_intencion(visitante, nuevas_filas):
    saludos, ayudas = _conteo("saludo"), _conteo("ayuda")
    for texto in ("hola", "buenas", "¿Qué puedo preguntar?"):
        _consultar(visitante, texto)
    assert (_conteo("saludo") - saludos, _conteo("ayuda") - ayudas) == (2, 1)


def test_cada_registro_del_resumen_trae_su_intencion(visitante, nuevas_filas):
    _consultar(visitante, "¿Cómo son las hojas del pejibaye?")
    with SessionLocal() as db:
        [registro] = tiempos.resumen(db, dias=1, solo_lentas=False, limite=1).registros
    assert registro.id == nuevas_filas()[0]["id"]
    assert registro.intencion == IntencionConsulta.DESCRIPCION
