"""Pruebas de RR_00_06 — recuperación de contraseña.

Usan la BD del contenedor a través de la API. El envío de correo se reemplaza
por una función que guarda los mensajes, así que no sale ningún correo real.
Cada prueba borra las cuentas que crea (el borrado arrastra sus tokens). Se
ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
import re

import pytest

from apoyo import SesionFalsa, api, crear_cuenta_verificada, usuario_falso
from apoyo import sql as _sql
from app.routers import auth
from app.schemas.auth import CorreoRequest

VIEJA = "Vieja#2024"
NUEVA = "Nueva#2025x"


@pytest.fixture
def correo(correos_de_prueba):
    """Una cuenta activa y verificada con la contraseña VIEJA."""
    direccion = correos_de_prueba("recup")
    crear_cuenta_verificada(direccion, VIEJA)
    return direccion


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
    desactivada = SesionFalsa(usuario_falso(activo=False, estado="inactivo"))
    salida = auth.recuperar_password(CorreoRequest(correo="ana@test.com"), desactivada)
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
