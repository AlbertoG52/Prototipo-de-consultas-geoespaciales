"""Pruebas de RR_00_07 — verificación de correo electrónico.

Usan la BD del contenedor a través de la API. El envío de correo se reemplaza
por una función que guarda los mensajes, así que no sale ningún correo real.
Cada prueba borra las cuentas que crea (el borrado arrastra sus tokens). Se
ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.routers import auth

PASSWORD = "Clave#2024"

api = TestClient(app)


def _sql(consulta: str, **parametros):
    with SessionLocal() as db:
        resultado = db.execute(text(consulta), parametros)
        db.commit()
        return resultado


@pytest.fixture
def buzon(monkeypatch):
    """Reemplaza el envío: cada correo queda en esta lista como (destino, texto)."""
    enviados = []
    monkeypatch.setattr(
        auth, "enviar_correo", lambda destino, _asunto, texto, _html=None: enviados.append((destino, texto))
    )
    return enviados


@pytest.fixture
def correo():
    direccion = f"verif-{uuid.uuid4().hex[:10]}@test.com"
    yield direccion
    _sql("DELETE FROM usuarios WHERE correo = :c", c=direccion)


def _registrar(correo):
    return api.post("/auth/registro", json={"nombre": "Ana", "correo": correo, "password": PASSWORD})


def _login(correo):
    return api.post("/auth/login", json={"correo": correo, "password": PASSWORD})


def _token_del_enlace(texto: str) -> str:
    return re.search(r"/verify-email\?token=([\w-]+)", texto).group(1)


def test_el_registro_envia_el_enlace_y_la_cuenta_nace_sin_verificar(buzon, correo):
    # Criterio 1: se envía un enlace al correo durante el registro.
    salida = _registrar(correo)
    assert salida.status_code == 201
    assert salida.json()["usuario"]["correo_verificado"] is False
    assert len(buzon) == 1 and buzon[0][0] == correo
    assert _token_del_enlace(buzon[0][1])


def test_sin_verificar_no_puede_iniciar_sesion(buzon, correo):
    # Criterio 2: acceso limitado hasta completar la verificación.
    _registrar(correo)
    salida = _login(correo)
    assert salida.status_code == 403
    assert "verificar tu correo" in salida.json()["detail"]


def test_el_enlace_verifica_y_habilita_la_cuenta(buzon, correo):
    # Criterio 3: se valida el correo antes de habilitar la cuenta.
    _registrar(correo)
    token = _token_del_enlace(buzon[0][1])

    assert api.post("/auth/verificar", json={"token": token}).status_code == 200
    assert _login(correo).status_code == 200


def test_el_enlace_solo_sirve_una_vez(buzon, correo):
    _registrar(correo)
    token = _token_del_enlace(buzon[0][1])
    api.post("/auth/verificar", json={"token": token})
    assert api.post("/auth/verificar", json={"token": token}).status_code == 400


def test_enlace_inventado_se_rechaza():
    assert api.post("/auth/verificar", json={"token": "no-existe"}).status_code == 400


def test_enlace_vencido_se_rechaza(buzon, correo):
    _registrar(correo)
    token = _token_del_enlace(buzon[0][1])
    _sql(
        "UPDATE tokens SET expira_en = now() - interval '1 minute' "
        "WHERE usuario_id = (SELECT id FROM usuarios WHERE correo = :c)",
        c=correo,
    )
    assert api.post("/auth/verificar", json={"token": token}).status_code == 400
    assert _login(correo).status_code == 403


def test_en_la_bd_no_se_guarda_el_token_del_enlace(buzon, correo):
    _registrar(correo)
    token = _token_del_enlace(buzon[0][1])
    guardados = _sql(
        "SELECT token FROM tokens WHERE usuario_id = (SELECT id FROM usuarios WHERE correo = :c)",
        c=correo,
    ).scalars().all()
    assert guardados and token not in guardados


def test_reenviar_anula_el_enlace_anterior(buzon, correo):
    _registrar(correo)
    viejo = _token_del_enlace(buzon[0][1])
    # Se salta la espera entre reenvíos haciendo "viejo" el primer token.
    _sql(
        "UPDATE tokens SET creado_en = now() - interval '2 minutes' "
        "WHERE usuario_id = (SELECT id FROM usuarios WHERE correo = :c)",
        c=correo,
    )

    assert api.post("/auth/reenviar-verificacion", json={"correo": correo}).status_code == 200
    assert len(buzon) == 2
    nuevo = _token_del_enlace(buzon[1][1])

    assert api.post("/auth/verificar", json={"token": viejo}).status_code == 400
    assert api.post("/auth/verificar", json={"token": nuevo}).status_code == 200


def test_reenviar_espera_entre_envios(buzon, correo):
    _registrar(correo)
    api.post("/auth/reenviar-verificacion", json={"correo": correo})
    assert len(buzon) == 1  # el del registro; el reenvío inmediato no sale


def test_reenviar_no_revela_si_el_correo_existe(buzon, correo):
    _registrar(correo)
    existe = api.post("/auth/reenviar-verificacion", json={"correo": correo}).json()
    no_existe = api.post("/auth/reenviar-verificacion", json={"correo": "nadie-xyz@test.com"}).json()
    assert existe == no_existe


def test_si_el_correo_falla_la_cuenta_igual_se_crea(monkeypatch, correo):
    def fallar(*_args, **_kwargs):
        raise OSError("SMTP caído")

    monkeypatch.setattr(auth, "enviar_correo", fallar)
    salida = _registrar(correo)
    assert salida.status_code == 201
    assert "no pudimos enviar" in salida.json()["mensaje"]
