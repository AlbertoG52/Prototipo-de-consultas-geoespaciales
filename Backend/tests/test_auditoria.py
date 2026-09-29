"""Pruebas de RR_00_09 — auditoría de acciones administrativas.

Las de registro e inmutabilidad usan la BD del contenedor y deshacen todo al
terminar, así que no dejan datos. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import SessionLocal
from app.routers.admin import _usuario_a_modificar


def test_no_puede_modificarse_a_si_mismo():
    actual = SimpleNamespace(id=7)
    with pytest.raises(HTTPException) as error:
        _usuario_a_modificar(7, actual, db=None)
    assert error.value.status_code == 409


@pytest.fixture
def db():
    """Sesión cuyos cambios se descartan siempre al final."""
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()


def _crear_usuario(db, correo: str) -> int:
    return db.execute(
        text(
            "INSERT INTO usuarios (correo, password_hash, rol_id) "
            "VALUES (:c, 'x', (SELECT id FROM roles WHERE nombre = 'usuario')) RETURNING id"
        ),
        {"c": correo},
    ).scalar()


def test_cambio_registra_accion_fecha_afectado_y_actor(db):
    actor = _crear_usuario(db, "actor.prueba@example.com")
    afectado = _crear_usuario(db, "afectado.prueba@example.com")

    db.execute(text("SELECT set_config('app.actor_id', :id, true)"), {"id": str(actor)})
    db.execute(
        text("UPDATE usuarios SET rol_id = (SELECT id FROM roles WHERE nombre = 'moderador') WHERE id = :id"),
        {"id": afectado},
    )

    fila = db.execute(
        text("SELECT accion, detalle, fecha, actor_id FROM auditoria WHERE usuario_afectado_id = :id"),
        {"id": afectado},
    ).one()
    assert fila.accion == "cambio_rol"
    assert fila.detalle == "usuario -> moderador"
    assert fila.fecha is not None
    assert fila.actor_id == actor


@pytest.mark.parametrize("sentencia", ["UPDATE auditoria SET detalle = 'x'", "DELETE FROM auditoria", "TRUNCATE auditoria"])
def test_registro_no_se_puede_modificar(db, sentencia):
    afectado = _crear_usuario(db, "inmutable.prueba@example.com")
    db.execute(text("UPDATE usuarios SET estado = 'inactivo' WHERE id = :id"), {"id": afectado})

    with pytest.raises(DBAPIError, match="no se puede modificar"):
        db.execute(text(sentencia))
