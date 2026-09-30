"""Pruebas de RR_00_05 — bloqueo temporal por intentos fallidos de inicio de sesión.

No necesitan base de datos: se llama al endpoint con un usuario y una sesión
simulados. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.config import INTENTOS_LOGIN_MAXIMOS, MINUTOS_BLOQUEO_LOGIN
from app.routers import auth
from app.schemas.usuario import LoginRequest
from app.security import hash_password

CORRECTA = "Correcta#2024"
INCORRECTA = "Incorrecta#2024"


class _SesionFalsa:
    """Imita lo que usa el login: query(...).filter(...).first() y commit()."""

    def __init__(self, usuario):
        self.usuario = usuario
        self.commits = 0

    def query(self, _modelo):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return self.usuario

    def commit(self):
        self.commits += 1


def _usuario(**extra):
    datos = dict(
        id=7,
        correo="ana@test.com",
        nombre="Ana",
        password_hash=hash_password(CORRECTA),
        rol=SimpleNamespace(nombre="usuario"),
        estado="activo",
        activo=True,
        minutos_inactividad=None,
        intentos_fallidos=0,
        bloqueado_hasta=None,
        correo_verificado=True,
    )
    datos.update(extra)
    return SimpleNamespace(**datos)


def _login(db, password):
    return auth.iniciar_sesion(LoginRequest(correo="ana@test.com", password=password), db)


def _fallar(db):
    with pytest.raises(HTTPException) as err:
        _login(db, INCORRECTA)
    return err.value


def test_cada_fallo_suma_un_intento():
    usuario = _usuario()
    db = _SesionFalsa(usuario)
    error = _fallar(db)
    assert error.status_code == 401
    assert usuario.intentos_fallidos == 1
    assert usuario.bloqueado_hasta is None


def test_se_bloquea_al_llegar_al_maximo():
    # Criterio 1: la cuenta se bloquea tras varios intentos fallidos.
    usuario = _usuario()
    db = _SesionFalsa(usuario)
    for _ in range(INTENTOS_LOGIN_MAXIMOS - 1):
        assert _fallar(db).status_code == 401

    error = _fallar(db)
    assert error.status_code == 423
    assert usuario.bloqueado_hasta > datetime.now(timezone.utc)
    # Criterio 3: el mensaje dice cuánto dura el bloqueo.
    assert f"{MINUTOS_BLOQUEO_LOGIN} minuto" in error.detail


def test_bloqueada_rechaza_incluso_la_password_correcta():
    usuario = _usuario(bloqueado_hasta=datetime.now(timezone.utc) + timedelta(minutes=3))
    db = _SesionFalsa(usuario)
    with pytest.raises(HTTPException) as err:
        _login(db, CORRECTA)
    assert err.value.status_code == 423
    assert "3 minutos" in err.value.detail


def test_bloqueo_vencido_permite_entrar_y_reinicia():
    usuario = _usuario(
        intentos_fallidos=2,
        bloqueado_hasta=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db = _SesionFalsa(usuario)
    salida = _login(db, CORRECTA)
    assert salida.access_token
    assert usuario.intentos_fallidos == 0
    assert usuario.bloqueado_hasta is None


def test_login_correcto_reinicia_el_contador():
    usuario = _usuario(intentos_fallidos=INTENTOS_LOGIN_MAXIMOS - 1)
    db = _SesionFalsa(usuario)
    _login(db, CORRECTA)
    assert usuario.intentos_fallidos == 0


def test_correo_inexistente_responde_igual_que_password_incorrecta():
    db = _SesionFalsa(None)
    error = _fallar(db)
    assert error.status_code == 401
    assert error.detail == "Correo o contraseña incorrectos."
    assert db.commits == 0


def test_minutos_de_bloqueo_redondea_hacia_arriba():
    ahora = datetime.now(timezone.utc)
    usuario = _usuario(bloqueado_hasta=ahora + timedelta(seconds=61))
    assert auth._minutos_de_bloqueo(usuario, ahora) == 2
    assert auth._minutos_de_bloqueo(_usuario(), ahora) is None
