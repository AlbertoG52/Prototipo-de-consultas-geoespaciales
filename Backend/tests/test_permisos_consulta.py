"""Pruebas de RR_77 — tipos de consulta permitidos por rol (services/permisos.py).

Tres grupos:

- Sin BD: el rol de cada persona, el mensaje y los ejemplos que se sugieren.
- El servicio sobre la BD: cambiar los permisos deja registros en 'auditoria',
  que no se pueden borrar (RR_00_09), así que corren en la sesión `sesion` de
  conftest.py, que se deshace al final.
- Por la API: para no cambiar la configuración real, `permisos.de` se
  reemplaza por una que bloquea lo que pide cada prueba. Las demás pruebas del
  proyecto permiten todo (fixture `todos_los_tipos_permitidos` de conftest.py);
  las que leen la tabla de verdad llevan la marca `permisos_de_la_bd`.

Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from httpx import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import config
from app.dominio import (
    EstadoConsulta,
    MotivoOrientacion,
    NombreRol,
    RolDeConsulta,
    TipoPregunta,
    TipoSesion,
)
from app.models import Usuario
from app.schemas.consulta import RespuestaConsulta
from app.schemas.permisos import CambioPermisos
from app.security import Identidad
from app.services import permisos
from app.services.catalogo import CatalogoDemo
from app.services.consultas import _Resultado
from app.services.preprocesamiento import EJEMPLOS_DE_CONSULTA

from apoyo import (
    VISITANTE,
    CatalogoQueNoSeUsa,
    api,
    crear_cuenta_verificada,
    crear_usuario,
    iniciar_sesion,
    sql,
    usuario_falso,
)

PASSWORD = "Clave#2024"
DESCRIPCION = "¿Cómo son las hojas de Quercus costaricensis?"
DISTRIBUCION = "¿Dónde crece Quercus costaricensis?"
AMBIGUA = "guaria"  # Guaria morada y Guaria naranja (catálogo de demostración)
NARANJA = "guarianthe-aurantiaca"


def _identidad(rol: str | None) -> Identidad:
    if rol is None:
        return VISITANTE
    return Identidad(tipo=TipoSesion.USUARIO, sesion_id="s-1", usuario=usuario_falso(rol=rol))


def _sin(
    *bloqueados: TipoPregunta, rol: RolDeConsulta = RolDeConsulta.VISITANTE
) -> permisos.Permisos:
    return permisos.Permisos(rol=rol, permitidos=permisos.TODOS - set(bloqueados))


# --- sin BD ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [
        (None, RolDeConsulta.VISITANTE),
        (NombreRol.USUARIO, RolDeConsulta.USUARIO),
        (NombreRol.MODERADOR, RolDeConsulta.MODERADOR),
        (NombreRol.SUPERMODERADOR, None),  # siempre puede todo
    ],
)
def test_el_rol_que_se_configura(rol, esperado):
    assert permisos.rol_de(_identidad(rol)) == esperado


@pytest.mark.permisos_de_la_bd
def test_el_supermoderador_puede_todo_sin_leer_la_bd():
    # La sesión es None: si se consultara la tabla, fallaría.
    assert permisos.de(None, _identidad(NombreRol.SUPERMODERADOR)).permitidos == permisos.TODOS


def test_el_mensaje_dice_que_tipo_falta_y_cuales_tiene():
    # Criterio 3.
    mensaje = _sin(TipoPregunta.DESCRIPCION, rol=RolDeConsulta.USUARIO).mensaje(
        TipoPregunta.DESCRIPCION
    )
    assert mensaje == (
        "Tu rol (usuario) no tiene habilitadas las consultas de descripción. "
        "Puedes preguntar por: distribución, hábitat e información general."
    )


def test_el_mensaje_del_visitante():
    mensaje = _sin(TipoPregunta.HABITAT, TipoPregunta.GENERAL).mensaje(TipoPregunta.HABITAT)
    assert mensaje.startswith("Como visitante sin cuenta no tienes habilitadas")
    assert mensaje.endswith("Puedes preguntar por: distribución y descripción.")


def test_el_mensaje_sin_ningun_tipo():
    mensaje = _sin(*TipoPregunta).mensaje(TipoPregunta.GENERAL)
    assert mensaje.endswith("Por ahora no tienes habilitado ningún tipo de consulta.")


def test_solo_se_sugieren_ejemplos_de_tipos_permitidos():
    resultado = _Resultado(
        estado=EstadoConsulta.ORIENTACION,
        motivo=MotivoOrientacion.SALUDO,
        permitidos=permisos.TODOS - {TipoPregunta.DESCRIPCION},
    )
    assert resultado.ejemplos == [e for e in EJEMPLOS_DE_CONSULTA if "hojas" not in e]


# --- el servicio sobre la BD (fixture `sesion` de conftest.py) -----------------------


def _solo(rol: RolDeConsulta, *permitidos: TipoPregunta) -> CambioPermisos:
    return CambioPermisos.model_validate({"roles": [{"rol": rol, "permitidos": permitidos}]})


@pytest.mark.permisos_de_la_bd
def test_el_supermoderador_define_los_tipos_de_un_rol(sesion):
    # Criterio 1, y aplica desde la siguiente consulta (criterio 2).
    actor = crear_usuario(sesion, "actor.permisos@example.com", NombreRol.SUPERMODERADOR)
    moderador = crear_usuario(sesion, "moderador.permisos@example.com", NombreRol.MODERADOR)

    salida = permisos.cambiar(
        sesion, actor, _solo(RolDeConsulta.MODERADOR, TipoPregunta.DISTRIBUCION)
    )

    del_moderador = next(r for r in salida.roles if r.rol == RolDeConsulta.MODERADOR)
    assert del_moderador.permitidos == [TipoPregunta.DISTRIBUCION]
    assert salida.actualizado_por == "actor.permisos@example.com"
    identidad = Identidad(tipo=TipoSesion.USUARIO, sesion_id="s", usuario=moderador)
    assert permisos.de(sesion, identidad).permitidos == {TipoPregunta.DISTRIBUCION}


def test_cambiar_un_rol_no_toca_los_demas(sesion):
    actor = crear_usuario(sesion, "actor.permisos@example.com", NombreRol.SUPERMODERADOR)
    antes = {r.rol: r.permitidos for r in permisos.ver(sesion).roles}

    salida = permisos.cambiar(sesion, actor, _solo(RolDeConsulta.VISITANTE))

    despues = {r.rol: r.permitidos for r in salida.roles}
    assert despues[RolDeConsulta.VISITANTE] == []
    assert despues[RolDeConsulta.USUARIO] == antes[RolDeConsulta.USUARIO]
    assert despues[RolDeConsulta.MODERADOR] == antes[RolDeConsulta.MODERADOR]


def _auditoria_de(db: Session, actor: Usuario) -> list[tuple[str, str]]:
    filas = db.execute(
        text("SELECT accion, detalle FROM auditoria WHERE actor_id = :a ORDER BY id"),
        {"a": actor.id},
    )
    return [tuple(f) for f in filas]


def test_cada_cambio_queda_en_la_auditoria_con_quien_lo_hizo(sesion):
    actor = crear_usuario(sesion, "actor.permisos@example.com", NombreRol.SUPERMODERADOR)
    todos = list(TipoPregunta)
    permisos.cambiar(sesion, actor, _solo(RolDeConsulta.USUARIO, *todos))  # parte de todo
    previas = len(_auditoria_de(sesion, actor))

    sin_descripcion = [t for t in todos if t != TipoPregunta.DESCRIPCION]
    permisos.cambiar(sesion, actor, _solo(RolDeConsulta.USUARIO, *sin_descripcion))
    # Guardar lo mismo otra vez no es un cambio: no deja otro registro.
    permisos.cambiar(sesion, actor, _solo(RolDeConsulta.USUARIO, *sin_descripcion))

    assert _auditoria_de(sesion, actor)[previas:] == [
        ("cambio_permiso", "usuario · descripción: permitido -> no permitido")
    ]


# --- por la API (fixtures `visitante` y `catalogo` de conftest.py) ---------------------

NO_PERMITIDA = (EstadoConsulta.ORIENTACION, MotivoOrientacion.TIPO_NO_PERMITIDO)


@pytest.fixture
def bloquear(monkeypatch):
    """Hace que `permisos.de` bloquee esos tipos para cualquiera, con el rol que tenga."""

    def aplicar(*tipos: TipoPregunta) -> None:
        original = permisos.de

        def de(db: Session, identidad: Identidad) -> permisos.Permisos:
            rol = permisos.rol_de(identidad)
            return original(db, identidad) if rol is None else _sin(*tipos, rol=rol)

        monkeypatch.setattr(permisos, "de", de)

    return aplicar


def _consultar(cabeceras: dict[str, str], texto: str, **extra: object) -> Response:
    return api.post("/consultas", headers=cabeceras, json={"texto": texto, **extra})


@pytest.mark.parametrize("catalogo", [CatalogoQueNoSeUsa], indirect=True)
def test_un_tipo_no_permitido_no_se_busca_ni_se_cobra(visitante, bloquear, catalogo):
    # Criterios 2 y 3.
    bloquear(TipoPregunta.DESCRIPCION)
    datos = _consultar(visitante, DESCRIPCION).json()
    assert (datos["estado"], datos["motivo"]) == NO_PERMITIDA
    assert datos["mensaje"] == _sin(TipoPregunta.DESCRIPCION).mensaje(TipoPregunta.DESCRIPCION)
    assert datos["respuesta"] is None
    assert datos["consultas_restantes"] == config.LIMITE_CONSULTAS_ANONIMO
    assert all("hojas" not in e for e in datos["ejemplos"])


def test_los_tipos_permitidos_se_responden(visitante, bloquear):
    bloquear(TipoPregunta.DESCRIPCION)
    assert _consultar(visitante, DISTRIBUCION).json()["estado"] == EstadoConsulta.RESUELTA


class CatalogoQueResponde:
    """El catálogo de demostración, pero su respuesta trae otro tipo, como cuando
    CR-BioLM lo precisa con su vocabulario (RR_29)."""

    def __init__(self, tipo: TipoPregunta):
        self.demo, self.tipo = CatalogoDemo(), tipo

    def __getattr__(self, nombre: str) -> object:
        return getattr(self.demo, nombre)

    def construir_respuesta(self, especie_id: str, texto: str) -> RespuestaConsulta | None:
        respuesta = self.demo.construir_respuesta(especie_id, texto)
        return respuesta.model_copy(update={"tipo": self.tipo}) if respuesta else None


@pytest.mark.parametrize(
    "catalogo", [lambda: CatalogoQueResponde(TipoPregunta.HABITAT)], indirect=True
)
def test_se_revisa_tambien_el_tipo_de_la_respuesta(visitante, bloquear, catalogo):
    bloquear(TipoPregunta.HABITAT)
    datos = _consultar(visitante, DISTRIBUCION).json()
    assert (datos["estado"], datos["motivo"]) == NO_PERMITIDA
    assert datos["respuesta"] is None
    assert datos["consultas_restantes"] == config.LIMITE_CONSULTAS_ANONIMO


@pytest.fixture
def cuenta(correos_de_prueba):
    correo = correos_de_prueba("permisos")
    crear_cuenta_verificada(correo, PASSWORD)
    return iniciar_sesion(correo, PASSWORD)


def _restantes(cabeceras: dict[str, str]) -> int:
    return api.get("/auth/sesion", headers=cabeceras).json()["consultas_restantes"]


def test_con_cuenta_queda_en_la_conversacion_sin_cobrar(cuenta, bloquear):
    bloquear(TipoPregunta.DESCRIPCION)
    inicio = _restantes(cuenta)
    datos = _consultar(cuenta, DESCRIPCION).json()

    assert datos["mensaje"].startswith("Tu rol (usuario) no tiene habilitadas")
    assert _restantes(cuenta) == inicio
    detalle = api.get(f"/conversaciones/{datos['conversacion_id']}", headers=cuenta).json()
    [guardada] = detalle["consultas"]
    assert (guardada["estado"], guardada["motivo"]) == NO_PERMITIDA


def test_una_ambigua_pendiente_no_se_resuelve_si_ya_no_esta_permitida(cuenta, bloquear):
    inicio = _restantes(cuenta)
    pendiente = _consultar(cuenta, AMBIGUA).json()
    assert pendiente["estado"] == EstadoConsulta.AMBIGUA

    bloquear(TipoPregunta.GENERAL)  # "guaria" solo nombra la especie
    elegida = _consultar(cuenta, AMBIGUA, consulta_id=pendiente["id"], especie_id=NARANJA)

    assert elegida.status_code == 403
    assert "información general" in elegida.json()["detail"]
    assert _restantes(cuenta) == inicio
    detalle = api.get(f"/conversaciones/{pendiente['conversacion_id']}", headers=cuenta).json()
    assert detalle["consultas"][0]["estado"] == EstadoConsulta.AMBIGUA  # sigue pendiente


def test_se_registra_el_tipo_que_se_pidio(visitante, bloquear):
    # RR_33: la intención es el tipo pedido, no el motivo.
    desde = sql("SELECT COALESCE(MAX(id), 0) FROM tiempos_respuesta").scalar()
    try:
        bloquear(TipoPregunta.DESCRIPCION)
        _consultar(visitante, DESCRIPCION)
        filas = sql(
            "SELECT intencion, resultado FROM tiempos_respuesta WHERE id > :d", d=desde
        ).all()
    finally:
        sql("DELETE FROM tiempos_respuesta WHERE id > :d", d=desde)
    assert [tuple(f) for f in filas] == [(TipoPregunta.DESCRIPCION, EstadoConsulta.ORIENTACION)]


# --- /admin/permisos-consulta ----------------------------------------------------------


@pytest.fixture
def supermoderador(correos_de_prueba):
    correo = correos_de_prueba("super")
    crear_cuenta_verificada(correo, PASSWORD, NombreRol.SUPERMODERADOR)
    return iniciar_sesion(correo, PASSWORD)


def test_el_panel_lee_los_tipos_de_cada_rol(supermoderador):
    datos = api.get("/admin/permisos-consulta", headers=supermoderador).json()
    assert [r["rol"] for r in datos["roles"]] == list(RolDeConsulta)
    for rol in datos["roles"]:
        assert set(rol["permitidos"]) <= set(TipoPregunta)


def test_solo_el_supermoderador_ve_los_permisos(cuenta):
    assert api.get("/admin/permisos-consulta", headers=cuenta).status_code == 403


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"roles": []},
        {"roles": [{"rol": NombreRol.SUPERMODERADOR, "permitidos": []}]},  # no se configura
        {"roles": [{"rol": "usuario", "permitidos": ["mapa"]}]},
        {"roles": [{"rol": "usuario", "permitidos": []}, {"rol": "usuario", "permitidos": []}]},
    ],
)
def test_cambios_invalidos_se_rechazan(supermoderador, cuerpo):
    salida = api.put("/admin/permisos-consulta", headers=supermoderador, json=cuerpo)
    assert salida.status_code == 422
