"""Fixtures comunes de las pruebas: las piezas que se preparan y se limpian solas.

Las que no necesitan limpieza están en apoyo.py.
"""

import uuid

import pytest

from app import config
from app.db import SessionLocal
from app.main import app
from app.routers import auth
from app.services.catalogo import obtener_catalogo

from apoyo import api, sql


@pytest.fixture(autouse=True)
def catalogo_de_demostracion(monkeypatch):
    """Todas las pruebas usan el catálogo de demostración, diga lo que diga el .env.

    Así no dependen de que CR-BioLM esté levantado ni de sus datos. Las que
    prueban CR-BioLM (test_catalogo_crbiolm.py) cambian a 'crbiolm' con su
    propio servidor falso.
    """
    monkeypatch.setattr(config, "CATALOGO", "demo")


@pytest.fixture
def buzon(monkeypatch):
    """Reemplaza el envío de correos: cada uno queda en esta lista como (destino, texto)."""
    enviados = []
    monkeypatch.setattr(
        auth,
        "enviar_correo",
        lambda destino, _asunto, texto, _html=None: enviados.append((destino, texto)),
    )
    return enviados


@pytest.fixture
def correos_de_prueba():
    """Entrega correos únicos y, al terminar, borra las cuentas creadas con ellos.

    Una cuenta con registros en 'auditoria' no se puede borrar (RR_00_09), así
    que estas pruebas no deben cambiar el rol ni el estado de esas cuentas.
    """
    creados = []

    def nuevo(prefijo: str = "prueba") -> str:
        correo = f"{prefijo}-{uuid.uuid4().hex[:10]}@test.com"
        creados.append(correo)
        return correo

    yield nuevo
    for correo in creados:
        sql("DELETE FROM usuarios WHERE correo = :c", c=correo)


@pytest.fixture
def db():
    """Sesión de BD cuyos cambios se descartan siempre al final."""
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()


@pytest.fixture
def sesion(db, monkeypatch):
    """La sesión `db` sin confirmar nada: commit solo envía los cambios a la BD.

    Para probar servicios que confirman cambios que no se pueden borrar después,
    como los que dejan registros en 'auditoria' (RR_00_09).
    """
    monkeypatch.setattr(db, "commit", db.flush)
    return db


@pytest.fixture
def visitante():
    """Cabeceras de un visitante con sesión anónima nueva (RR_00_11)."""
    token = api.post("/auth/anonimo").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def catalogo(request):
    """Reemplaza el catálogo de la API por el que recibe con `indirect=True`."""
    app.dependency_overrides[obtener_catalogo] = request.param
    yield
    app.dependency_overrides.pop(obtener_catalogo, None)
