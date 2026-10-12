"""Endpoints de administración — RR_00_10, RR_00_09 y RR_57.

La dependencia de rol está en el router, no en cada endpoint: todo lo que se
agregue bajo /admin queda restringido al supermoderador sin tener que
repetirla. tests/test_roles.py falla si alguien la quita.

Los cambios de rol y de estado los registra en 'auditoria' el trigger de la
BD (003 y 011); aquí solo se indica quién actúa. El supermoderador no puede
modificarse a sí mismo, para que no pueda quedarse sin acceso. No se cubre el
caso de dos supermoderadores que se degradan mutuamente al mismo tiempo; si
llegara a importar, la protección debe ir en la BD bloqueando filas.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..dominio import NombreRol
from ..models import Rol, Usuario
from ..schemas.admin import CambioEstado, CambioRol, RegistroAuditoria, ResumenTiempos
from ..schemas.usuario import UsuarioOut
from ..security import obtener_usuario_actual, requiere_rol
from ..services import tiempos

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(requiere_rol(NombreRol.SUPERMODERADOR))],
)


def _usuario_a_modificar(usuario_id: int, actual: Usuario, db: Session) -> Usuario:
    """Busca el usuario y deja registrado en la transacción quién actúa.

    set_config(..., true) vive solo hasta el commit: el trigger de auditoría
    lo lee para llenar 'actor_id'.
    """
    if usuario_id == actual.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes modificar tu propio rol ni tu estado.",
        )
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario no existe.")
    db.execute(text("SELECT set_config('app.actor_id', :id, true)"), {"id": str(actual.id)})
    return usuario


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    """Usuarios registrados, en orden de creación.

    Sin paginación: suficiente para el prototipo. Con muchos usuarios habrá
    que agregar límite y desplazamiento.
    """
    usuarios = db.query(Usuario).options(joinedload(Usuario.rol)).order_by(Usuario.id.asc()).all()
    return [UsuarioOut.de_modelo(u) for u in usuarios]


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado(
    usuario_id: int,
    datos: CambioEstado,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Activa o desactiva una cuenta. La desactivada queda fuera en su siguiente petición."""
    usuario = _usuario_a_modificar(usuario_id, actual, db)
    usuario.estado = datos.estado
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.de_modelo(usuario)


@router.patch("/usuarios/{usuario_id}/rol", response_model=UsuarioOut)
def cambiar_rol(
    usuario_id: int,
    datos: CambioRol,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Cambia el rol de una cuenta. Aplica en su siguiente petición."""
    usuario = _usuario_a_modificar(usuario_id, actual, db)
    usuario.rol_id = db.query(Rol.id).filter(Rol.nombre == datos.rol).scalar()
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.de_modelo(usuario)


@router.get("/auditoria", response_model=list[RegistroAuditoria])
def listar_auditoria(limite: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    """RR_00_09 — registro de acciones administrativas, del más reciente al más antiguo.

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


@router.get("/tiempos", response_model=ResumenTiempos)
def tiempos_de_respuesta(
    dias: int = Query(7, ge=1, le=365),
    solo_lentas: bool = Query(False),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """RR_57 — tiempo de respuesta de las consultas, para el equipo técnico.

    Resumen de los últimos `dias` días y las consultas más recientes; con
    `solo_lentas=true`, solo las que superaron SEGUNDOS_RESPUESTA_LENTA.
    """
    return tiempos.resumen(db, dias, solo_lentas, limite)
