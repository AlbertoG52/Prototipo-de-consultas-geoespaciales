"""Pruebas de RR_61 — asignación del rol por defecto al registrarse.

Usan la BD del contenedor a través de la API; el envío de correo se reemplaza
(fixture `buzon`) y cada prueba borra las cuentas que crea. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest

from app.dominio import NombreRol
from app.schemas.usuario import MENSAJE_ROL_EN_REGISTRO

from apoyo import api, sql

PASSWORD = "Clave#2024"


def _registrar(correo, **extra):
    datos = {"nombre": "Ana", "correo": correo, "password": PASSWORD, **extra}
    return api.post("/auth/registro", json=datos)


def _rol_guardado(correo) -> str | None:
    return sql(
        "SELECT r.nombre FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.correo = :c",
        c=correo,
    ).scalar()


def test_la_cuenta_nueva_es_de_usuario_estandar(buzon, correos_de_prueba):
    # Criterio 1: toda cuenta creada recibe el rol de usuario estándar.
    correo = correos_de_prueba("rol")
    salida = _registrar(correo)
    assert salida.status_code == 201
    assert salida.json()["usuario"]["rol"] == NombreRol.USUARIO


def test_el_rol_queda_guardado_con_la_cuenta(buzon, correos_de_prueba):
    # Criterio 2: el rol asignado queda registrado junto con la cuenta.
    correo = correos_de_prueba("rol")
    _registrar(correo)
    assert _rol_guardado(correo) == NombreRol.USUARIO


@pytest.mark.parametrize(
    "campo",
    [
        {"rol": "supermoderador"},
        {"rol": "usuario"},  # tampoco se acepta pedir el rol que igual tocaría
        {"rol_id": 3},
        {"role": "moderador"},
    ],
)
def test_no_se_puede_elegir_el_rol_al_registrarse(buzon, correos_de_prueba, campo):
    # Criterio 3: se rechaza la petición y no se crea la cuenta.
    correo = correos_de_prueba("rol")
    salida = _registrar(correo, **campo)
    assert salida.status_code == 422
    assert MENSAJE_ROL_EN_REGISTRO in salida.json()["detail"][0]["msg"]
    assert _rol_guardado(correo) is None
    assert buzon == []


def test_otros_campos_de_mas_tambien_se_rechazan(buzon, correos_de_prueba):
    correo = correos_de_prueba("rol")
    assert _registrar(correo, es_admin=True).status_code == 422
    assert _rol_guardado(correo) is None
