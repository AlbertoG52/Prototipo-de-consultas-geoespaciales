"""Pruebas de RR_00_04 — expiración de la sesión por inactividad.

No necesitan base de datos: se usan usuarios y peticiones simulados. Se
ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt
from pydantic import ValidationError
from starlette.requests import Request

from app.config import (
    ALGORITMO_JWT,
    MINUTOS_INACTIVIDAD_SESION,
    MINUTOS_TOKEN_SIN_INACTIVIDAD,
    SECRET_KEY,
)
from app.routers import auth, perfil
from app.schemas.perfil import CambioInactividadRequest
from app.security import (
    TIPO_USUARIO,
    Identidad,
    crear_token_usuario,
    minutos_inactividad_de,
    obtener_identidad,
)


class _SesionFalsa:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        pass


def _usuario(minutos=None):
    return SimpleNamespace(
        id=7,
        correo="ana@test.com",
        nombre="Ana",
        rol=SimpleNamespace(nombre="usuario"),
        minutos_inactividad=minutos,
        activo=True,
    )


def _duracion_minutos(token: str) -> float:
    """Minutos que faltan para que venza el token."""
    datos = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITMO_JWT])
    vence = datetime.fromtimestamp(datos["exp"], tz=timezone.utc)
    return (vence - datetime.now(timezone.utc)).total_seconds() / 60


def _peticion(token: str | None) -> Request:
    cabeceras = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request({"type": "http", "headers": cabeceras})


# --- criterio 2: el periodo es configurable -------------------------------

def test_sin_preferencia_usa_el_valor_del_sistema():
    assert minutos_inactividad_de(_usuario(None)) == MINUTOS_INACTIVIDAD_SESION


def test_la_preferencia_del_perfil_manda():
    assert minutos_inactividad_de(_usuario(60)) == 60
    assert minutos_inactividad_de(_usuario(0)) == 0


@pytest.mark.parametrize("minutos", [30, 60, 1440])
def test_el_token_vence_con_el_periodo_del_usuario(minutos):
    token, _ = crear_token_usuario(_usuario(minutos))
    assert minutos - 1 < _duracion_minutos(token) <= minutos


def test_nunca_usa_un_vencimiento_largo():
    token, _ = crear_token_usuario(_usuario(0))
    assert _duracion_minutos(token) > MINUTOS_TOKEN_SIN_INACTIVIDAD - 1


@pytest.mark.parametrize("invalido", [-5, 1, 45, 99999])
def test_solo_se_aceptan_las_opciones_del_perfil(invalido):
    with pytest.raises(ValidationError):
        CambioInactividadRequest(minutos=invalido)


def test_cambiar_inactividad_guarda_y_devuelve_token_con_el_nuevo_periodo():
    usuario, db = _usuario(30), _SesionFalsa()
    identidad = Identidad(tipo=TIPO_USUARIO, sesion_id="abc", usuario=usuario)
    salida = perfil.cambiar_inactividad(CambioInactividadRequest(minutos=360), identidad, usuario, db)
    assert usuario.minutos_inactividad == 360 and db.commits == 1
    assert 359 < _duracion_minutos(salida.access_token) <= 360
    # Sigue siendo la misma sesión (RR_09 depende del sesion_id).
    assert jwt.decode(salida.access_token, SECRET_KEY, algorithms=[ALGORITMO_JWT])["sid"] == "abc"


# --- criterio 1: la actividad renueva; sin ella, la sesión se cierra ------

def test_renovar_conserva_la_sesion_y_reinicia_el_periodo():
    usuario = _usuario(30)
    token, sid = crear_token_usuario(usuario)
    identidad = Identidad(tipo=TIPO_USUARIO, sesion_id=sid, usuario=usuario)
    nuevo = auth.renovar_sesion(identidad, usuario).access_token
    assert jwt.decode(nuevo, SECRET_KEY, algorithms=[ALGORITMO_JWT])["sid"] == sid
    assert 29 < _duracion_minutos(nuevo) <= 30


def test_token_vencido_se_marca_como_invalido():
    vencido = jwt.encode(
        {
            "sub": "7",
            "tipo": TIPO_USUARIO,
            "sid": "abc",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        SECRET_KEY,
        algorithm=ALGORITMO_JWT,
    )
    identidad = obtener_identidad(_peticion(vencido), db=None)
    assert identidad.usuario is None and identidad.token_invalido


def test_sin_token_no_es_una_sesion_expirada():
    identidad = obtener_identidad(_peticion(None), db=None)
    assert not identidad.token_invalido


# --- criterio 3: después de expirar hay que volver a autenticarse ---------

def test_estado_de_sesion_con_token_vencido_responde_401():
    identidad = Identidad(tipo="anonimo", sesion_id="", token_invalido=True)
    with pytest.raises(HTTPException) as error:
        auth.estado_sesion(identidad, db=None)
    assert error.value.status_code == 401


def test_renovar_exige_una_cuenta():
    # Un token vencido no llega a renovar_sesion: la dependencia responde 401.
    from app.security import obtener_usuario_actual

    ruta = next(r for r in auth.router.routes if r.path.endswith("/renovar"))
    assert obtener_usuario_actual in {d.call for d in ruta.dependant.dependencies}
