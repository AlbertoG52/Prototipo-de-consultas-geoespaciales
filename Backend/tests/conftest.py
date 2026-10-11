"""Fixtures comunes de las pruebas: las piezas que se preparan y se limpian solas.

Las que no necesitan limpieza están en apoyo.py.
"""

import uuid

import pytest

from app.db import SessionLocal
from app.routers import auth

from apoyo import sql


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
