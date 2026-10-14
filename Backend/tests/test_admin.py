"""Pruebas de RR_69 a RR_76 — administración de usuarios por el supermoderador.

Dos grupos:

- Las del servicio (services/admin.py) cambian roles y estados o crean consultas. Una cuenta con
  registros en 'auditoria' no se puede borrar (RR_00_09), así que corren en la
  sesión `db`, que se deshace al final, con `commit` reemplazado por `flush`:
  nada queda confirmado.
- Las de la API (/admin) solo leen o reciben un rechazo, así que pueden crear
  cuentas confirmadas que `correos_de_prueba` borra al terminar.

Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from starlette.requests import Request

from app import config
from app.db import SessionLocal
from app.dominio import EstadoConsulta, EstadoCuenta, MotivoOrientacion, NombreRol
from app.errores import Conflicto, NoEncontrado
from app.models import Consulta, Conversacion, Rol, Usuario
from app.routers import consultas
from app.security import crear_token_usuario, obtener_identidad, requiere_rol
from app.services import admin
from app.services.uso import limite_de
from app.tiempo import ahora

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


# --- RR_76: historial de uso por usuario --------------------------------------------


def _consultar(
    db: Session,
    usuario: Usuario,
    texto: str,
    estado: EstadoConsulta = EstadoConsulta.RESUELTA,
    dias_atras: int = 0,
    motivo: MotivoOrientacion | None = None,
) -> None:
    """Guarda una consulta de `usuario` como la deja services/consultas.py.

    Una de orientación necesita su `motivo` (restricción de la tabla 016).
    """
    momento = ahora() - timedelta(days=dias_atras)
    conversacion = Conversacion(usuario_id=usuario.id, titulo=texto)
    db.add(conversacion)
    db.flush()
    resuelta = estado == EstadoConsulta.RESUELTA
    respuesta = {"especie": {"nombre_cientifico": "Quercus costaricensis"}}
    db.add(
        Consulta(
            usuario_id=usuario.id,
            conversacion_id=conversacion.id,
            texto=texto,
            estado=estado,
            respuesta=respuesta if resuelta else None,
            resuelta_en=momento if resuelta else None,
            realizada_en=momento,
            motivo=motivo,
        )
    )
    db.flush()


@pytest.fixture
def con_historial(sesion):
    """Una cuenta con tres consultas (hoy, ayer y anteayer) y otra con una."""
    usuario = _crear(sesion, "historial.prueba@example.com")
    _consultar(sesion, usuario, "dónde crece el roble", EstadoConsulta.RESUELTA)
    _consultar(sesion, usuario, "cedro", EstadoConsulta.AMBIGUA, dias_atras=1)
    _consultar(sesion, usuario, "asdf", EstadoConsulta.SIN_COINCIDENCIAS, dias_atras=2)
    otro = _crear(sesion, "otro.prueba@example.com")
    _consultar(sesion, otro, "consulta de otra persona")
    return usuario


def test_historial_trae_solo_las_consultas_de_esa_cuenta(sesion, con_historial):
    historial = admin.historial_de_uso(sesion, con_historial.id, limite=20, desplazamiento=0)

    assert historial.usuario.correo == "historial.prueba@example.com"
    assert [c.texto for c in historial.consultas] == ["dónde crece el roble", "cedro", "asdf"]
    assert historial.total == 3


def test_historial_trae_estado_y_especie_de_cada_consulta(sesion, con_historial):
    historial = admin.historial_de_uso(sesion, con_historial.id, limite=20, desplazamiento=0)

    assert [c.estado for c in historial.consultas] == [
        EstadoConsulta.RESUELTA,
        EstadoConsulta.AMBIGUA,
        EstadoConsulta.SIN_COINCIDENCIAS,
    ]
    # La especie solo se conoce si la consulta se resolvió.
    assert [c.especie for c in historial.consultas] == ["Quercus costaricensis", None, None]


def test_historial_por_paginas(sesion, con_historial):
    pagina = admin.historial_de_uso(sesion, con_historial.id, limite=2, desplazamiento=2)

    assert pagina.total == 3
    assert [c.texto for c in pagina.consultas] == ["asdf"]


def test_el_texto_se_oculta_si_la_configuracion_lo_pide(sesion, con_historial, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_VE_TEXTO_CONSULTAS", False)

    historial = admin.historial_de_uso(sesion, con_historial.id, limite=20, desplazamiento=0)

    assert historial.texto_visible is False
    assert all(c.texto is None for c in historial.consultas)
    # Lo demás se sigue viendo: cuándo, con qué resultado y de qué especie.
    assert historial.consultas[0].estado == EstadoConsulta.RESUELTA
    assert historial.consultas[0].especie == "Quercus costaricensis"


def test_historial_de_usuario_inexistente(sesion):
    with pytest.raises(NoEncontrado):
        admin.historial_de_uso(sesion, -1, limite=20, desplazamiento=0)


# --- RR_76 criterio 3: uso por rol ----------------------------------------------------


def _uso(sesion: Session, rol: NombreRol):
    return next(u for u in admin.uso_por_rol(sesion) if u.rol == rol)


def test_uso_por_rol_suma_cuentas_y_consultas_de_cada_rol(sesion):
    """La BD de desarrollo ya tiene datos: se compara antes y después."""
    usuarios_antes = _uso(sesion, NombreRol.USUARIO)
    moderadores_antes = _uso(sesion, NombreRol.MODERADOR)

    moderador = _crear(sesion, "mod.prueba@example.com", NombreRol.MODERADOR)
    usuario = _crear(sesion, "usu.prueba@example.com")
    _crear(sesion, "sin-consultas.prueba@example.com")
    _consultar(sesion, moderador, "roble")
    _consultar(sesion, usuario, "cedro amargo")
    _consultar(sesion, usuario, "asdf", EstadoConsulta.SIN_COINCIDENCIAS)

    usuarios, moderadores = _uso(sesion, NombreRol.USUARIO), _uso(sesion, NombreRol.MODERADOR)
    assert usuarios.usuarios - usuarios_antes.usuarios == 2
    assert usuarios.consultas - usuarios_antes.consultas == 2
    assert moderadores.usuarios - moderadores_antes.usuarios == 1
    assert moderadores.consultas - moderadores_antes.consultas == 1


def test_las_orientaciones_se_ven_en_el_historial_pero_no_cuentan_como_uso(sesion):
    """RR_37 y RR_40: un saludo o un pedido de ayuda no es uso del agente."""
    usuario = _crear(sesion, "orientacion.prueba@example.com")
    antes = _uso(sesion, NombreRol.USUARIO)
    _consultar(sesion, usuario, "roble")
    _consultar(sesion, usuario, "hola", EstadoConsulta.ORIENTACION, motivo=MotivoOrientacion.SALUDO)

    assert _uso(sesion, NombreRol.USUARIO).consultas - antes.consultas == 1
    historial = admin.historial_de_uso(sesion, usuario.id, limite=20, desplazamiento=0)
    assert historial.total == 2
    assert EstadoConsulta.ORIENTACION in {c.estado for c in historial.consultas}


def test_uso_por_rol_trae_todos_los_roles(sesion):
    assert {u.rol for u in admin.uso_por_rol(sesion)} == set(NombreRol)


def test_la_api_entrega_historial_y_uso_por_rol(correos_de_prueba):
    correo = correos_de_prueba("super")
    crear_cuenta_verificada(correo, PASSWORD, NombreRol.SUPERMODERADOR)
    cabeceras = _cabeceras(correo)
    with SessionLocal() as db:
        propio_id = db.query(Usuario.id).filter_by(correo=correo).scalar()

    historial = api.get(f"/admin/usuarios/{propio_id}/consultas", headers=cabeceras)
    inexistente = api.get("/admin/usuarios/-1/consultas", headers=cabeceras)
    uso = api.get("/admin/uso-por-rol", headers=cabeceras)

    assert historial.status_code == 200
    assert historial.json()["total"] == 0
    assert inexistente.status_code == 404
    assert uso.status_code == 200
    assert {u["rol"] for u in uso.json()} == set(NombreRol)
