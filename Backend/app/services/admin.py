"""Administración de usuarios por el supermoderador — RR_69 a RR_76 y RR_00_09.

El router (routers/admin.py) exige el rol de supermoderador para todo /admin
(RR_69 criterio 1, RR_71 criterio 2, RR_73 criterio 1) y llama a estas
funciones:

- RR_71: `listar_usuarios` — correo, rol y estado de cada cuenta.
- RR_70: `cambiar_rol` — el rol se lee de la BD en cada petición
  (security.obtener_identidad), así que el cambio aplica de inmediato y el
  nuevo rol decide los permisos y el límite diario (services/uso.py).
- RR_74 / RR_75: `cambiar_estado` — una cuenta inactiva recibe 403 en su
  siguiente petición, incluida POST /consultas; al reactivarla conserva su rol.
  La persona puede seguir usando el agente sin cuenta, como cualquier visitante.
- RR_76: `historial_de_uso` (criterios 1 y 2) — las consultas de una cuenta.
  El texto de cada consulta solo se entrega si ADMIN_VE_TEXTO_CONSULTAS está
  encendido (config.py); si no, se ve cuándo consultó, con qué resultado y de
  qué especie. `uso_por_rol` (criterio 3) — cuántas consultas hicieron las
  cuentas de cada rol.
- RR_00_09: `listar_auditoria` — los cambios de rol y de estado los registra
  el trigger de la BD (003 y 011); aquí solo se indica quién actúa. Los cambios
  de límite de un rol también (018).
- RR_63: `listar_roles` y `configurar_limite` — el supermoderador define
  cuántas consultas tiene cada rol y cada cuánto se restablecen (RR_64). Aplica
  a la siguiente consulta de cada cuenta, porque el rol y su límite se leen de
  la BD en cada petición (services/uso.py). No se aceptan límites que dejen al
  usuario estándar con tantas consultas como el moderador o con menos que un
  visitante (RR_62 criterio 3 y RR_00_11 criterio 3).

RR_72 (búsqueda por correo y filtro por rol) se resuelve en el panel sobre el
listado completo.

El supermoderador no puede modificarse a sí mismo (RR_70 criterio 2), para que
no pueda quedarse sin acceso. No se cubre el caso de dos supermoderadores que
se degradan mutuamente al mismo tiempo; si llegara a importar, la protección
debe ir en la BD bloqueando filas.
"""

from __future__ import annotations

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from .. import config
from ..dominio import EstadoConsulta, EstadoCuenta, NombreRol, PeriodoConsultas
from ..errores import Conflicto, NoEncontrado, SolicitudInvalida
from ..models import Consulta, Rol, Usuario
from ..schemas.admin import (
    ConsultaDeUsuario,
    HistorialUso,
    RegistroAuditoria,
    RolOut,
    UsoDeRol,
)
from ..schemas.usuario import UsuarioOut
from .uso import DIAS_DEL_PERIODO, POR_PERIODO

MENSAJE_SOBRE_SI_MISMO = "No puedes modificar tu propio rol ni tu estado."


# --- RR_69 a RR_75: usuarios, roles y estados ------------------------------------


def listar_usuarios(db: Session) -> list[UsuarioOut]:
    """RR_71 — usuarios registrados, en orden de creación.

    Sin paginación: suficiente para el prototipo. Con muchos usuarios habrá
    que agregar límite y desplazamiento.
    """
    usuarios = db.query(Usuario).options(joinedload(Usuario.rol)).order_by(Usuario.id.asc()).all()
    return [UsuarioOut.de_modelo(u) for u in usuarios]


def cambiar_rol(db: Session, actor: Usuario, usuario_id: int, rol: NombreRol) -> UsuarioOut:
    """RR_70 — cambia el rol de una cuenta. Aplica en su siguiente petición."""
    usuario = _usuario_a_modificar(db, actor, usuario_id)
    rol_id = db.query(Rol.id).filter(Rol.nombre == rol).scalar()
    if rol_id is None:
        raise NoEncontrado("El rol no existe.")
    usuario.rol_id = rol_id
    return _guardar(db, usuario)


def cambiar_estado(
    db: Session, actor: Usuario, usuario_id: int, estado: EstadoCuenta
) -> UsuarioOut:
    """RR_74 y RR_75 — desactiva o reactiva una cuenta.

    La desactivada queda fuera en su siguiente petición; la reactivada vuelve
    con el rol que tenía, porque el estado no toca el rol.
    """
    usuario = _usuario_a_modificar(db, actor, usuario_id)
    usuario.estado = estado
    return _guardar(db, usuario)


# --- RR_63: límite de consultas por rol ------------------------------------------


def listar_roles(db: Session) -> list[RolOut]:
    """Los roles con su límite y periodo, en el orden en que se crearon."""
    return [_rol_out(r) for r in db.query(Rol).order_by(Rol.id).all()]


def configurar_limite(
    db: Session, actor: Usuario, nombre: NombreRol, limite: int, periodo: PeriodoConsultas
) -> RolOut:
    """RR_63 — define el límite de consultas de un rol y su periodo (RR_64).

    Los roles se bloquean mientras se valida, para que dos cambios a la vez no
    dejen límites que juntos no cumplen las reglas.
    """
    roles = {r.nombre: r for r in db.query(Rol).with_for_update().all()}
    rol = roles.get(nombre)
    if rol is None:
        raise NoEncontrado("El rol no existe.")
    limites = {
        n: (r.limite_consultas, PeriodoConsultas(r.periodo_consultas)) for n, r in roles.items()
    }
    limites[nombre] = (limite, periodo)
    _validar_limites(limites, cambiado=nombre)

    # El trigger de auditoría (018) lee quién actúa, igual que en los cambios de usuario.
    db.execute(text("SELECT set_config('app.actor_id', :id, true)"), {"id": str(actor.id)})
    rol.limite_consultas = limite
    rol.periodo_consultas = periodo
    db.commit()
    db.refresh(rol)
    return _rol_out(rol)


def _validar_limites(limites: dict[str, tuple[int, PeriodoConsultas]], cambiado: NombreRol) -> None:
    """RR_62 criterio 3 y RR_00_11 criterio 3, comparando los límites como consultas por día.

    Así se pueden comparar periodos distintos: 20 por día son más que 100 por semana.
    Se compara con enteros (a/b < c/d  ⇔  a·d < c·b) para que no haya redondeos y el
    mínimo o máximo que sugiere el mensaje sea exactamente el que se acepta.

    El mensaje dice qué valor sí se acepta con el periodo elegido, para el rol que se
    está cambiando (`cambiado`), así el supermoderador no tiene que calcularlo.
    """
    usuario = limites.get(NombreRol.USUARIO)
    if usuario is None:
        return
    limite_u, periodo_u = usuario
    dias_u = DIAS_DEL_PERIODO[periodo_u]

    moderador = limites.get(NombreRol.MODERADOR)
    if moderador is not None:
        limite_m, periodo_m = moderador
        dias_m = DIAS_DEL_PERIODO[periodo_m]
        if limite_u * dias_m >= limite_m * dias_u:  # usuario por día >= moderador por día
            if cambiado == NombreRol.MODERADOR:
                minimo = limite_u * dias_m // dias_u + 1
                sugerencia = f"{_por(periodo_m)}, el moderador necesita al menos {minimo}."
            else:
                maximo = (limite_m * dias_u - 1) // dias_m
                sugerencia = (
                    f"{_por(periodo_u)}, el máximo es {maximo}."
                    if maximo >= 1
                    else f"{_por(periodo_u)} no hay un límite posible; prueba otro periodo."
                )
            raise SolicitudInvalida(
                f"El límite del usuario estándar ({_texto_limite(*usuario)}) debe ser menor que "
                f"el del moderador ({_texto_limite(*moderador)}). {sugerencia}"
            )

    anonimo = config.LIMITE_CONSULTAS_ANONIMO  # por día, del .env
    if limite_u <= anonimo * dias_u:  # usuario por día <= visitante por día
        minimo = anonimo * dias_u + 1
        raise SolicitudInvalida(
            f"El usuario estándar ({_texto_limite(*usuario)}) debe tener más consultas que un "
            f"visitante sin cuenta ({anonimo} por día). "
            f"{_por(periodo_u)}, el mínimo es {minimo}."
        )


def _por(periodo: PeriodoConsultas) -> str:
    """'Por día', 'Por semana', 'Por mes' (al inicio de una oración)."""
    return POR_PERIODO[periodo].capitalize()


def _texto_limite(limite: int, periodo: PeriodoConsultas) -> str:
    return f"{limite} {POR_PERIODO[periodo]}"


def _rol_out(rol: Rol) -> RolOut:
    return RolOut(
        nombre=NombreRol(rol.nombre),
        descripcion=rol.descripcion,
        limite_consultas=rol.limite_consultas,
        periodo_consultas=PeriodoConsultas(rol.periodo_consultas),
    )


def listar_auditoria(db: Session, limite: int) -> list[RegistroAuditoria]:
    """RR_00_09 — acciones administrativas, de la más reciente a la más antigua.

    Solo lectura: la BD rechaza cualquier modificación de 'auditoria' (011).
    """
    filas = db.execute(
        text(
            """
            SELECT a.id, a.accion, a.detalle, a.fecha,
                   afectado.correo AS afectado, actor.correo AS actor
            FROM auditoria a
            LEFT JOIN usuarios afectado ON afectado.id = a.usuario_afectado_id
            LEFT JOIN usuarios actor    ON actor.id    = a.actor_id
            ORDER BY a.id DESC
            LIMIT :limite
            """
        ),
        {"limite": limite},
    ).mappings()
    return [RegistroAuditoria(**f) for f in filas]


def _usuario_a_modificar(db: Session, actor: Usuario, usuario_id: int) -> Usuario:
    """Busca el usuario y deja registrado en la transacción quién actúa.

    set_config(..., true) vive solo hasta el commit: el trigger de auditoría
    lo lee para llenar 'actor_id'.
    """
    if usuario_id == actor.id:
        raise Conflicto(MENSAJE_SOBRE_SI_MISMO)
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontrado("El usuario no existe.")
    db.execute(text("SELECT set_config('app.actor_id', :id, true)"), {"id": str(actor.id)})
    return usuario


def _guardar(db: Session, usuario: Usuario) -> UsuarioOut:
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.de_modelo(usuario)


# --- RR_76: historial de uso -------------------------------------------------------


def historial_de_uso(
    db: Session, usuario_id: int, limite: int, desplazamiento: int
) -> HistorialUso:
    """RR_76 criterios 1 y 2 — las consultas de una cuenta, de la más reciente a la más antigua.

    Trae `limite` consultas a partir de `desplazamiento`; `total` permite pedir
    las siguientes.
    """
    usuario = db.query(Usuario).options(joinedload(Usuario.rol)).filter_by(id=usuario_id).first()
    if usuario is None:
        raise NoEncontrado("El usuario no existe.")

    de_la_cuenta = Consulta.usuario_id == usuario_id
    total = db.query(func.count(Consulta.id)).filter(de_la_cuenta).scalar() or 0
    pagina = (
        db.query(Consulta)
        .filter(de_la_cuenta)
        .order_by(Consulta.realizada_en.desc(), Consulta.id.desc())
        .offset(desplazamiento)
        .limit(limite)
        .all()
    )
    ver_texto = config.ADMIN_VE_TEXTO_CONSULTAS
    return HistorialUso(
        usuario=UsuarioOut.de_modelo(usuario),
        texto_visible=ver_texto,
        total=total,
        consultas=[_consulta_de_usuario(c, ver_texto) for c in pagina],
    )


def uso_por_rol(db: Session) -> list[UsoDeRol]:
    """RR_76 criterio 3 — cuántas cuentas tiene cada rol y cuántas consultas hicieron.

    Cuenta las consultas guardadas (las mismas que muestra el historial), según
    el rol que la cuenta tiene hoy: si cambió de rol, todas sus consultas
    cuentan para el rol nuevo. No cuenta las de orientación (saludos, ayuda...,
    RR_37 y RR_40): se ven en el historial, pero no son uso del agente.
    """
    cuentas = (
        db.query(Rol.nombre, func.count(Usuario.id))
        .outerjoin(Usuario, Usuario.rol_id == Rol.id)
        .group_by(Rol.nombre)
        .tuples()
        .all()
    )
    consultas = (
        db.query(Rol.nombre, func.count(Consulta.id))
        .join(Usuario, Usuario.rol_id == Rol.id)
        .join(Consulta, Consulta.usuario_id == Usuario.id)
        .filter(Consulta.estado != EstadoConsulta.ORIENTACION)
        .group_by(Rol.nombre)
        .tuples()
        .all()
    )
    por_cuentas, por_consultas = dict(cuentas), dict(consultas)
    return [
        UsoDeRol(
            rol=NombreRol(nombre),
            usuarios=por_cuentas.get(nombre, 0),
            consultas=por_consultas.get(nombre, 0),
        )
        for (nombre,) in db.query(Rol.nombre).order_by(Rol.id).tuples()
    ]


def _consulta_de_usuario(consulta: Consulta, ver_texto: bool) -> ConsultaDeUsuario:
    especie = (consulta.respuesta or {}).get("especie") or {}
    return ConsultaDeUsuario(
        id=consulta.id,
        texto=consulta.texto if ver_texto else None,
        estado=EstadoConsulta(consulta.estado),
        especie=especie.get("nombre_cientifico"),
        realizada_en=consulta.realizada_en,
    )
