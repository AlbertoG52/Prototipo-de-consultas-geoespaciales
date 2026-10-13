"""Pruebas de RR_69 a RR_75 — administración de usuarios por el supermoderador.

Dos grupos:

- Las del servicio (services/admin.py) cambian roles y estados. Una cuenta con
  registros en 'auditoria' no se puede borrar (RR_00_09), así que corren en la
  sesión `db`, que se deshace al final, con `commit` reemplazado por `flush`:
  nada queda confirmado.
- Las de la API (/admin) solo leen o reciben un rechazo, así que pueden crear
  cuentas confirmadas que `correos_de_prueba` borra al terminar.

Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from starlette.requests import Request

from app.db import SessionLocal
from app.dominio import EstadoCuenta, NombreRol
from app.errores import Conflicto, NoEncontrado
from app.models import Rol, Usuario
from app.routers import consultas
from app.security import crear_token_usuario, obtener_identidad, requiere_rol
from app.services import admin
from app.services.uso import limite_de

from apoyo import api, crear_cuenta_verificada

PASSWORD = "Prueba123!"


# --- apoyo ---------------------------------------------------------------------


@pytest.fixture
def sesion(db, monkeypatch):
    """La sesión `db` sin confirmar nada: commit solo envía los cambios a la BD."""
    monkeypatch.setattr(db, "commit", db.flush)
    return db


def _crear(db: Session, correo: str, rol: NombreRol = NombreRol.USUARIO) -> Usuario:
    usuario_id = db.execute(
        text(
            "INSERT INTO usuarios (correo, password_hash, rol_id, correo_verificado) "
            "VALUES (:c, 'x', (SELECT id FROM roles WHERE nombre = :r), true) RETURNING id"
        ),
        {"c": correo, "r": rol},
    ).scalar_one()
    usuario = db.get(Usuario, usuario_id)
    assert usuario is not None
    return usuario


def _peticion(usuario: Usuario) -> Request:
    """Una petición con el token de `usuario`, como la que llega a cualquier endpoint."""
    token, _ = crear_token_usuario(usuario)
    return Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})


def _limite_del_rol(db: Session, rol: NombreRol) -> int:
    return db.query(Rol.limite_consultas).filter(Rol.nombre == rol).one()[0]


def _cabeceras(correo: str) -> dict[str, str]:
    """Token de una cuenta ya confirmada en la BD."""
    with SessionLocal() as db:
        usuario = db.query(Usuario).options(joinedload(Usuario.rol)).filter_by(correo=correo).one()
        token, _ = crear_token_usuario(usuario)
    return {"Authorization": f"Bearer {token}"}


# --- RR_71: listado de usuarios ------------------------------------------------


def test_listado_trae_correo_rol_y_estado(sesion):
    _crear(sesion, "listado.prueba@example.com", NombreRol.MODERADOR)

    listado = {u.correo: u for u in admin.listar_usuarios(sesion)}

    fila = listado["listado.prueba@example.com"]
    assert fila.rol == NombreRol.MODERADOR
    assert fila.estado == EstadoCuenta.ACTIVO


# --- RR_69 y RR_70: el cambio de rol ---------------------------------------------


def test_cambio_de_rol_aplica_en_la_siguiente_peticion(sesion):
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)
    afectado = _crear(sesion, "afectado.prueba@example.com")

    salida = admin.cambiar_rol(sesion, actor, afectado.id, NombreRol.MODERADOR)

    assert salida.rol == NombreRol.MODERADOR
    # La identidad se lee de la BD en cada petición, no del token (RR_69 criterio 3).
    identidad = obtener_identidad(_peticion(afectado), sesion)
    assert identidad.usuario is not None
    assert identidad.usuario.rol.nombre == NombreRol.MODERADOR


def test_el_nuevo_rol_decide_los_permisos(sesion):
    """RR_70 criterio 3: permisos de /admin y límite diario del nuevo rol."""
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)
    afectado = _crear(sesion, "afectado.prueba@example.com")
    solo_supermoderador = requiere_rol(NombreRol.SUPERMODERADOR)
    with pytest.raises(HTTPException):
        solo_supermoderador(afectado)

    admin.cambiar_rol(sesion, actor, afectado.id, NombreRol.SUPERMODERADOR)

    identidad = obtener_identidad(_peticion(afectado), sesion)
    assert identidad.usuario is not None
    assert solo_supermoderador(identidad.usuario) is identidad.usuario
    assert limite_de(identidad) == _limite_del_rol(sesion, NombreRol.SUPERMODERADOR)


@pytest.mark.parametrize(
    ("cambiar", "valor"),
    [
        (admin.cambiar_rol, NombreRol.USUARIO),
        (admin.cambiar_estado, EstadoCuenta.INACTIVO),
    ],
)
def test_no_puede_modificarse_a_si_mismo(sesion, cambiar, valor):
    """RR_70 criterio 2: ni su rol ni su estado, para no quedarse sin acceso."""
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)

    with pytest.raises(Conflicto):
        cambiar(sesion, actor, actor.id, valor)

    sesion.refresh(actor)
    assert actor.rol.nombre == NombreRol.SUPERMODERADOR
    assert actor.estado == EstadoCuenta.ACTIVO


def test_usuario_inexistente(sesion):
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)
    with pytest.raises(NoEncontrado):
        admin.cambiar_rol(sesion, actor, -1, NombreRol.MODERADOR)


def test_el_cambio_queda_en_la_auditoria_con_quien_lo_hizo(sesion):
    """RR_00_09: el servicio le dice al trigger quién actúa."""
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)
    afectado = _crear(sesion, "afectado.prueba@example.com")

    admin.cambiar_rol(sesion, actor, afectado.id, NombreRol.MODERADOR)

    fila = sesion.execute(
        text("SELECT accion, actor_id FROM auditoria WHERE usuario_afectado_id = :id"),
        {"id": afectado.id},
    ).one()
    assert fila.accion == "cambio_rol"
    assert fila.actor_id == actor.id


# --- RR_74 y RR_75: desactivar y reactivar ----------------------------------------


def test_cuenta_desactivada_queda_fuera_en_su_siguiente_peticion(sesion):
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)
    afectado = _crear(sesion, "afectado.prueba@example.com")

    salida = admin.cambiar_estado(sesion, actor, afectado.id, EstadoCuenta.INACTIVO)

    assert salida.estado == EstadoCuenta.INACTIVO  # criterio 3
    with pytest.raises(HTTPException) as error:
        obtener_identidad(_peticion(afectado), sesion)
    assert error.value.status_code == 403


def test_enviar_una_consulta_pasa_por_la_identidad():
    """RR_74 criterio 2: POST /consultas resuelve la identidad, que rechaza la cuenta inactiva."""
    ruta = next(r for r in consultas.router.routes if "POST" in getattr(r, "methods", ()))
    assert any(d.call is obtener_identidad for d in ruta.dependant.dependencies)


def test_cuenta_reactivada_recupera_su_rol(sesion):
    actor = _crear(sesion, "actor.prueba@example.com", NombreRol.SUPERMODERADOR)
    afectado = _crear(sesion, "afectado.prueba@example.com", NombreRol.MODERADOR)
    admin.cambiar_estado(sesion, actor, afectado.id, EstadoCuenta.INACTIVO)

    salida = admin.cambiar_estado(sesion, actor, afectado.id, EstadoCuenta.ACTIVO)

    assert salida.estado == EstadoCuenta.ACTIVO
    assert salida.rol == NombreRol.MODERADOR
    identidad = obtener_identidad(_peticion(afectado), sesion)  # criterio 3: de inmediato
    assert identidad.usuario is not None
    assert identidad.usuario.rol.nombre == NombreRol.MODERADOR


# --- La API: RR_69 criterio 1, RR_71 criterio 2 y la traducción de errores ---------


@pytest.mark.parametrize("rol", [NombreRol.USUARIO, NombreRol.MODERADOR])
def test_otros_roles_no_acceden_a_la_administracion(correos_de_prueba, rol):
    correo = correos_de_prueba("sin-permiso")
    crear_cuenta_verificada(correo, PASSWORD, rol)

    respuesta = api.get("/admin/usuarios", headers=_cabeceras(correo))

    assert respuesta.status_code == 403


def test_supermoderador_ve_el_listado(correos_de_prueba):
    correo = correos_de_prueba("super")
    crear_cuenta_verificada(correo, PASSWORD, NombreRol.SUPERMODERADOR)

    respuesta = api.get("/admin/usuarios", headers=_cabeceras(correo))

    assert respuesta.status_code == 200
    propia = next(u for u in respuesta.json() if u["correo"] == correo)
    assert propia["rol"] == NombreRol.SUPERMODERADOR
    assert propia["estado"] == EstadoCuenta.ACTIVO


def test_la_api_traduce_los_errores_del_servicio(correos_de_prueba):
    correo = correos_de_prueba("super")
    crear_cuenta_verificada(correo, PASSWORD, NombreRol.SUPERMODERADOR)
    cabeceras = _cabeceras(correo)
    with SessionLocal() as db:
        propio_id = db.query(Usuario.id).filter_by(correo=correo).scalar()

    sobre_si = api.patch(
        f"/admin/usuarios/{propio_id}/rol", json={"rol": "usuario"}, headers=cabeceras
    )
    inexistente = api.patch(
        "/admin/usuarios/-1/estado", json={"estado": "inactivo"}, headers=cabeceras
    )

    assert sobre_si.status_code == 409
    assert sobre_si.json()["detail"] == admin.MENSAJE_SOBRE_SI_MISMO
    assert inexistente.status_code == 404
