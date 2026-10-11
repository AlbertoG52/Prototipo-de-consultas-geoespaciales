"""Pruebas de la página de perfil: cambiar el nombre y la contraseña.

No necesitan base de datos: se llaman los endpoints con un usuario y una
sesión simulados. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers import perfil
from app.schemas.perfil import CambioNombreRequest, CambioPasswordRequest
from app.security import obtener_usuario_actual, verificar_password

from apoyo import SesionFalsa as _SesionFalsa
from apoyo import usuario_falso

ACTUAL = "Actual#2024"
NUEVA = "Nueva#2025x"


def _usuario():
    return usuario_falso(password=ACTUAL)


# --- nombre --------------------------------------------------------------


def test_nombre_se_limpia():
    assert CambioNombreRequest(nombre="  Ana   María ").nombre == "Ana María"
    assert CambioNombreRequest(nombre="<b>Ana</b>\nPérez").nombre == "Ana Pérez"


@pytest.mark.parametrize("nombre", ["", "   ", "a", "<b></b>", "<script>x</script>"])
def test_nombre_muy_corto_se_rechaza(nombre):
    with pytest.raises(ValidationError):
        CambioNombreRequest(nombre=nombre)


def test_nombre_muy_largo_se_rechaza():
    with pytest.raises(ValidationError):
        CambioNombreRequest(nombre="x" * 121)


def test_cambiar_nombre_guarda_y_devuelve_el_usuario():
    usuario, db = _usuario(), _SesionFalsa()
    salida = perfil.cambiar_nombre(CambioNombreRequest(nombre="Ana Pérez"), usuario, db)
    assert usuario.nombre == "Ana Pérez"
    assert salida.nombre == "Ana Pérez" and salida.correo == "ana@test.com"
    assert db.commits == 1


# --- contraseña ----------------------------------------------------------


@pytest.mark.parametrize("debil", ["corta1!", "sinmayuscula1!", "SinNumero!", "SinSimbolo1"])
def test_nueva_password_usa_las_reglas_del_registro(debil):
    # RR_00_03 criterio 3: la validación también aplica al cambiar la contraseña.
    with pytest.raises(ValidationError):
        CambioPasswordRequest(password_actual=ACTUAL, password_nueva=debil)


def test_cambio_de_password_correcto():
    usuario, db = _usuario(), _SesionFalsa()
    perfil.cambiar_password(
        CambioPasswordRequest(password_actual=ACTUAL, password_nueva=NUEVA), usuario, db
    )
    assert verificar_password(NUEVA, usuario.password_hash)
    assert not verificar_password(ACTUAL, usuario.password_hash)
    assert NUEVA not in usuario.password_hash  # RR_00_02: nunca en claro
    assert db.commits == 1


def test_password_actual_incorrecta_se_rechaza():
    usuario, db = _usuario(), _SesionFalsa()
    hash_antes = usuario.password_hash
    with pytest.raises(HTTPException) as error:
        perfil.cambiar_password(
            CambioPasswordRequest(password_actual="Otra#2024", password_nueva=NUEVA), usuario, db
        )
    assert error.value.status_code == 400
    assert usuario.password_hash == hash_antes and db.commits == 0


def test_nueva_igual_a_la_actual_se_rechaza():
    usuario, db = _usuario(), _SesionFalsa()
    with pytest.raises(HTTPException) as error:
        perfil.cambiar_password(
            CambioPasswordRequest(password_actual=ACTUAL, password_nueva=ACTUAL), usuario, db
        )
    assert error.value.status_code == 400 and db.commits == 0


# --- acceso --------------------------------------------------------------


def test_todas_las_rutas_exigen_cuenta():
    # Si alguien quita la dependencia, un visitante anónimo podría llegar aquí.
    for ruta in perfil.router.routes:
        dependencias = {d.call for d in ruta.dependant.dependencies}
        assert obtener_usuario_actual in dependencias, ruta.path
