"""Pruebas de RR_00_06 — recuperación de contraseña.

Usan la BD del contenedor a través de la API. El envío de correo se reemplaza
por una función que guarda los mensajes, así que no sale ningún correo real.
Cada prueba borra las cuentas que crea (el borrado arrastra sus tokens). Se
ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
import re
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.routers import auth
from app.schemas.auth import RecuperarPasswordRequest
from app.security import hash_password

VIEJA = "Vieja#2024"
NUEVA = "Nueva#2025x"

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
    """Una cuenta activa y verificada con la contraseña VIEJA."""
    direccion = f"recup-{uuid.uuid4().hex[:10]}@test.com"
    _sql(
        "INSERT INTO usuarios (correo, password_hash, rol_id, correo_verificado) "
        "VALUES (:c, :h, (SELECT id FROM roles WHERE nombre = 'usuario'), true)",
        c=direccion,
        h=hash_password(VIEJA),
    )
    yield direccion
    _sql("DELETE FROM usuarios WHERE correo = :c", c=direccion)


def _pedir(correo):
    return api.post("/auth/recuperar", json={"correo": correo})


def _restablecer(token, password=NUEVA):
    return api.post("/auth/restablecer", json={"token": token, "password": password})


def _login(correo, password):
    return api.post("/auth/login", json={"correo": correo, "password": password})


def _token_del_enlace(texto: str) -> str:
    return re.search(r"/reset-password\?token=([\w-]+)", texto).group(1)


def test_pedir_envia_el_enlace_al_correo_registrado(buzon, correo):
    # Criterios 1 y 2: se solicita con el correo y llega un enlace.
    assert _pedir(correo).status_code == 200
    assert len(buzon) == 1 and buzon[0][0] == correo
    assert _token_del_enlace(buzon[0][1])


def test_el_enlace_permite_cambiar_la_contrasena(buzon, correo):
    # Criterio 3: nueva contraseña tras la validación.
    _pedir(correo)
    assert _restablecer(_token_del_enlace(buzon[0][1])).status_code == 200
    assert _login(correo, NUEVA).status_code == 200
    assert _login(correo, VIEJA).status_code == 401


def test_el_enlace_solo_sirve_una_vez(buzon, correo):
    _pedir(correo)
    token = _token_del_enlace(buzon[0][1])
    _restablecer(token)
    assert _restablecer(token, "Otra#2026xx").status_code == 400


def test_enlace_vencido_se_rechaza(buzon, correo):
    # Criterio 2: válido por tiempo limitado.
    _pedir(correo)
    token = _token_del_enlace(buzon[0][1])
    _sql(
        "UPDATE tokens SET expira_en = now() - interval '1 minute' "
        "WHERE usuario_id = (SELECT id FROM usuarios WHERE correo = :c)",
        c=correo,
    )
    assert _restablecer(token).status_code == 400
    assert _login(correo, VIEJA).status_code == 200


def test_el_enlace_de_verificacion_no_sirve_para_cambiar_la_contrasena(buzon, correo):
    _sql("UPDATE usuarios SET correo_verificado = false WHERE correo = :c", c=correo)
    api.post("/auth/reenviar-verificacion", json={"correo": correo})
    token = re.search(r"token=([\w-]+)", buzon[0][1]).group(1)
    assert _restablecer(token).status_code == 400


def test_la_nueva_contrasena_usa_las_reglas_del_registro(buzon, correo):
    _pedir(correo)
    salida = _restablecer(_token_del_enlace(buzon[0][1]), "debil")
    assert salida.status_code == 422
    # El token no se gastó: puede reintentar con una contraseña válida.
    assert _restablecer(_token_del_enlace(buzon[0][1])).status_code == 200


def test_no_revela_si_el_correo_existe(buzon, correo):
    existe = _pedir(correo).json()
    no_existe = _pedir("nadie-xyz@test.com").json()
    assert existe == no_existe
    assert len(buzon) == 1


def test_cuenta_desactivada_no_recibe_enlace(buzon):
    # Sin BD: desactivar una cuenta real deja un registro de auditoría que no
    # se puede borrar (RR_00_09), así que se simula el usuario.
    class _SesionFalsa:
        def query(self, _modelo):
            return self

        def filter(self, *_args):
            return self

        def first(self):
            return SimpleNamespace(id=1, correo="ana@test.com", activo=False)

    salida = auth.recuperar_password(RecuperarPasswordRequest(correo="ana@test.com"), _SesionFalsa())
    assert salida.mensaje == _pedir("nadie-xyz@test.com").json()["mensaje"]
    assert buzon == []


def test_espera_entre_solicitudes(buzon, correo):
    _pedir(correo)
    _pedir(correo)
    assert len(buzon) == 1


def test_quita_el_bloqueo_y_verifica_el_correo(buzon, correo):
    _sql(
        "UPDATE usuarios SET bloqueado_hasta = now() + interval '10 minutes', "
        "intentos_fallidos = 3, correo_verificado = false WHERE correo = :c",
        c=correo,
    )
    _pedir(correo)
    _restablecer(_token_del_enlace(buzon[0][1]))
    assert _login(correo, NUEVA).status_code == 200
