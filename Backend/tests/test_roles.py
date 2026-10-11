"""Pruebas de RR_00_10 — control de acceso por rol.

No necesitan base de datos: se prueba la dependencia con usuarios simulados y
se verifica que el router de administración la tenga. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from fastapi import HTTPException

from app.dominio import NombreRol, TipoSesion
from app.routers import admin
from app.security import Identidad, obtener_usuario_actual, requiere_rol

from apoyo import usuario_falso


def _usuario(rol: str | None):
    return usuario_falso(rol=rol)


# --- criterio 1 y 2: se valida el rol y se rechaza lo no permitido ---------


def test_rol_permitido_pasa():
    verificar = requiere_rol(NombreRol.SUPERMODERADOR)
    usuario = _usuario(NombreRol.SUPERMODERADOR)
    assert verificar(usuario) is usuario


@pytest.mark.parametrize("rol", [NombreRol.USUARIO, NombreRol.MODERADOR, None])
def test_rol_no_permitido_recibe_403(rol):
    verificar = requiere_rol(NombreRol.SUPERMODERADOR)
    with pytest.raises(HTTPException) as error:
        verificar(_usuario(rol))
    assert error.value.status_code == 403


def test_el_moderador_no_hereda_permisos_del_supermoderador():
    verificar = requiere_rol(NombreRol.SUPERMODERADOR)
    with pytest.raises(HTTPException):
        verificar(_usuario(NombreRol.MODERADOR))


def test_varios_roles_permitidos():
    verificar = requiere_rol(NombreRol.MODERADOR, NombreRol.SUPERMODERADOR)
    for rol in (NombreRol.MODERADOR, NombreRol.SUPERMODERADOR):
        assert verificar(_usuario(rol)).rol.nombre == rol


def test_sin_roles_es_un_error_de_programacion():
    with pytest.raises(ValueError):
        requiere_rol()


def test_visitante_sin_cuenta_recibe_401():
    anonimo = Identidad(tipo=TipoSesion.ANONIMO, sesion_id="x", anon_id="x")
    with pytest.raises(HTTPException) as error:
        obtener_usuario_actual(anonimo)
    assert error.value.status_code == 401


# --- criterio 3: la validación vive en el servidor, para todo /admin --------


def test_router_admin_exige_rol_en_todos_sus_endpoints():
    """Si alguien quita la dependencia del router, esta prueba falla."""
    dependencias = [d.dependency for d in admin.router.dependencies]
    assert any(getattr(d, "__name__", "") == "verificar" for d in dependencias)

    # Y cada ruta del router la hereda.
    for ruta in admin.router.routes:
        heredadas = [d.call for d in ruta.dependant.dependencies]
        assert any(getattr(c, "__name__", "") == "verificar" for c in heredadas), ruta.path
