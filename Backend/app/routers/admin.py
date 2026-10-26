"""Endpoints de administración — RR_63, RR_69 a RR_76, RR_00_10, RR_00_09 y RR_57.

La dependencia de rol está en el router, no en cada endpoint: todo lo que se
agregue bajo /admin queda restringido al supermoderador sin tener que
repetirla (RR_69 criterio 1, RR_71 criterio 2). tests/test_roles.py falla si
alguien la quita.

La lógica vive en services/admin.py (usuarios, roles, estados y auditoría) y
services/tiempos.py (RR_57).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..dominio import NombreRol
from ..models import Usuario
from ..schemas.admin import (
    CambioEstado,
    CambioLimite,
    CambioRol,
    HistorialUso,
    RegistroAuditoria,
    ResumenTiempos,
    RolOut,
    UsoDeRol,
)
from ..schemas.usuario import UsuarioOut
from ..security import obtener_usuario_actual, requiere_rol
from ..services import admin, tiempos
from .errores import errores_http

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(requiere_rol(NombreRol.SUPERMODERADOR))],
)


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)) -> list[UsuarioOut]:
    """RR_71 — usuarios registrados con su correo, rol y estado."""
    return admin.listar_usuarios(db)


@router.get("/usuarios/{usuario_id}/consultas", response_model=HistorialUso)
def historial_de_uso(
    usuario_id: int,
    limite: int = Query(20, ge=1, le=100),
    desplazamiento: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> HistorialUso:
    """RR_76 criterios 1 y 2 — consultas de una cuenta, de la más reciente a la más antigua.

    El texto de cada consulta viene solo si ADMIN_VE_TEXTO_CONSULTAS está
    encendido (`texto_visible`).
    """
    with errores_http():
        return admin.historial_de_uso(db, usuario_id, limite, desplazamiento)


@router.get("/uso-por-rol", response_model=list[UsoDeRol])
def uso_por_rol(db: Session = Depends(get_db)) -> list[UsoDeRol]:
    """RR_76 criterio 3 — cuentas y consultas guardadas de cada rol."""
    return admin.uso_por_rol(db)


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado(
    usuario_id: int,
    datos: CambioEstado,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """RR_74 y RR_75 — activa o desactiva una cuenta (no la propia: 409)."""
    with errores_http():
        return admin.cambiar_estado(db, actual, usuario_id, datos.estado)


@router.patch("/usuarios/{usuario_id}/rol", response_model=UsuarioOut)
def cambiar_rol(
    usuario_id: int,
    datos: CambioRol,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """RR_70 — cambia el rol de una cuenta (no la propia: 409)."""
    with errores_http():
        return admin.cambiar_rol(db, actual, usuario_id, datos.rol)


@router.get("/roles", response_model=list[RolOut])
def listar_roles(db: Session = Depends(get_db)) -> list[RolOut]:
    """RR_63 — los roles con su límite de consultas y cada cuánto se restablece."""
    return admin.listar_roles(db)


@router.patch("/roles/{rol}", response_model=RolOut)
def configurar_limite(
    rol: NombreRol,
    datos: CambioLimite,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> RolOut:
    """RR_63 y RR_64 — define el límite de consultas de un rol y su periodo.

    Aplica a las consultas siguientes de las cuentas de ese rol. Responde 400 si
    el usuario estándar quedaría con tantas consultas como el moderador o con
    menos que un visitante (RR_62 criterio 3).
    """
    with errores_http():
        return admin.configurar_limite(
            db, actual, rol, datos.limite_consultas, datos.periodo_consultas
        )


@router.get("/auditoria", response_model=list[RegistroAuditoria])
def listar_auditoria(
    limite: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
) -> list[RegistroAuditoria]:
    """RR_00_09 — registro de acciones administrativas, del más reciente al más antiguo."""
    return admin.listar_auditoria(db, limite)


@router.get("/tiempos", response_model=ResumenTiempos)
def tiempos_de_respuesta(
    dias: int = Query(7, ge=1, le=365),
    solo_lentas: bool = Query(False),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ResumenTiempos:
    """RR_57 — tiempo de respuesta de las consultas, para el equipo técnico.

    Resumen de los últimos `dias` días y las consultas más recientes; con
    `solo_lentas=true`, solo las que superaron SEGUNDOS_RESPUESTA_LENTA.
    """
    return tiempos.resumen(db, dias, solo_lentas, limite)
