"""Administración de usuarios por el supermoderador — RR_69 a RR_75 y RR_00_09.

El router (routers/admin.py) exige el rol de supermoderador para todo /admin
(RR_69 criterio 1, RR_71 criterio 2) y llama a estas funciones:

- RR_71: `listar_usuarios` — correo, rol y estado de cada cuenta.
- RR_70: `cambiar_rol` — el rol se lee de la BD en cada petición
  (security.obtener_identidad), así que el cambio aplica de inmediato y el
  nuevo rol decide los permisos y el límite diario (services/uso.py).
- RR_74 / RR_75: `cambiar_estado` — una cuenta inactiva recibe 403 en su
  siguiente petición, incluida POST /consultas; al reactivarla conserva su rol.
- RR_00_09: `listar_auditoria` — los cambios de rol y de estado los registra
  el trigger de la BD (003 y 011); aquí solo se indica quién actúa.

RR_72 (búsqueda por correo y filtro por rol) se resuelve en el panel sobre el
listado completo.

El supermoderador no puede modificarse a sí mismo (RR_70 criterio 2), para que
no pueda quedarse sin acceso. No se cubre el caso de dos supermoderadores que
se degradan mutuamente al mismo tiempo; si llegara a importar, la protección
debe ir en la BD bloqueando filas.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from ..dominio import EstadoCuenta, NombreRol
from ..errores import Conflicto, NoEncontrado
from ..models import Rol, Usuario
from ..schemas.admin import RegistroAuditoria
from ..schemas.usuario import UsuarioOut

MENSAJE_SOBRE_SI_MISMO = "No puedes modificar tu propio rol ni tu estado."


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
