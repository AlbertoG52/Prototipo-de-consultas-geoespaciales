"""Endpoints de administración: usuarios, roles, límites, permisos, estadísticas, auditoría,
tiempos y respuestas.

La dependencia de rol está en el router: todo lo que se agregue bajo /admin queda
restringido al supermoderador. tests/test_roles.py falla si se quita. La lógica está en
services/admin.py, tiempos.py, preferencias.py, permisos.py y estadisticas.py.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..dominio import NombreRol, PeriodoEstadisticas
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
from ..schemas.estadisticas import EstadisticasUso, ResumenUso
from ..schemas.permisos import CambioPermisos, PermisosTiposConsulta
from ..schemas.preferencias import CambioPreferenciasPorDefecto, PreferenciasPorDefecto
from ..schemas.usuario import UsuarioOut
from ..security import obtener_usuario_actual, requiere_rol
from ..services import admin, estadisticas, permisos, preferencias, tiempos
from .errores import errores_http

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(requiere_rol(NombreRol.SUPERMODERADOR))],
)


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)) -> list[UsuarioOut]:
    """Usuarios registrados con su correo, rol y estado."""
    return admin.listar_usuarios(db)


@router.get("/usuarios/{usuario_id}/consultas", response_model=HistorialUso)
def historial_de_uso(
    usuario_id: int,
    limite: int = Query(20, ge=1, le=100),
    desplazamiento: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> HistorialUso:
    """Consultas de una cuenta, de la más reciente a la más antigua. El texto se incluye solo
    si ADMIN_VE_TEXTO_CONSULTAS está activo (`texto_visible`).
    """
    with errores_http():
        return admin.historial_de_uso(db, usuario_id, limite, desplazamiento)


@router.get("/uso-por-rol", response_model=list[UsoDeRol])
def uso_por_rol(db: Session = Depends(get_db)) -> list[UsoDeRol]:
    """Cuentas y consultas guardadas de cada rol."""
    return admin.uso_por_rol(db)


@router.get("/estadisticas", response_model=EstadisticasUso)
def estadisticas_de_uso(
    periodo: PeriodoEstadisticas = Query(PeriodoEstadisticas.TODO),
    db: Session = Depends(get_db),
) -> EstadisticasUso:
    """Total de consultas del periodo, por rol, por día y por tipo de pregunta."""
    return estadisticas.estadisticas(db, periodo)


@router.get("/estadisticas/resumen", response_model=ResumenUso)
def resumen_de_uso(db: Session = Depends(get_db)) -> ResumenUso:
    """Cifras de las tarjetas del panel: cuentas y consultas de hoy, ayer y 30 días."""
    return estadisticas.resumen(db)


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado(
    usuario_id: int,
    datos: CambioEstado,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Activa o desactiva una cuenta (no la propia: 409)."""
    with errores_http():
        return admin.cambiar_estado(db, actual, usuario_id, datos.estado)


@router.patch("/usuarios/{usuario_id}/rol", response_model=UsuarioOut)
def cambiar_rol(
    usuario_id: int,
    datos: CambioRol,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Cambia el rol de una cuenta (no la propia: 409)."""
    with errores_http():
        return admin.cambiar_rol(db, actual, usuario_id, datos.rol)


@router.get("/roles", response_model=list[RolOut])
def listar_roles(db: Session = Depends(get_db)) -> list[RolOut]:
    """Roles con su límite de consultas y su periodo."""
    return admin.listar_roles(db)


@router.patch("/roles/{rol}", response_model=RolOut)
def configurar_limite(
    rol: NombreRol,
    datos: CambioLimite,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> RolOut:
    """Define el límite de consultas de un rol y su periodo.

    Aplica a las consultas siguientes. Responde 400 si el usuario quedaría con tantas
    consultas como el moderador o con menos que un visitante.
    """
    with errores_http():
        return admin.configurar_limite(
            db, actual, rol, datos.limite_consultas, datos.periodo_consultas
        )


@router.get("/auditoria", response_model=list[RegistroAuditoria])
def listar_auditoria(
    limite: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
) -> list[RegistroAuditoria]:
    """Registro de acciones administrativas, del más reciente al más antiguo."""
    return admin.listar_auditoria(db, limite)


@router.get("/tiempos", response_model=ResumenTiempos)
def tiempos_de_respuesta(
    dias: int = Query(7, ge=1, le=365),
    solo_lentas: bool = Query(False),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ResumenTiempos:
    """Tiempos de respuesta de los últimos `dias` días y las consultas más recientes. Con
    `solo_lentas=true`, solo las que superaron SEGUNDOS_RESPUESTA_LENTA.
    """
    return tiempos.resumen(db, dias, solo_lentas, limite)


@router.get("/preferencias-respuesta", response_model=PreferenciasPorDefecto)
def ver_preferencias_por_defecto(db: Session = Depends(get_db)) -> PreferenciasPorDefecto:
    """Si las respuestas incluyen el mapa y las fuentes por defecto."""
    return preferencias.ver_por_defecto(db)


@router.put("/preferencias-respuesta", response_model=PreferenciasPorDefecto)
def cambiar_preferencias_por_defecto(
    datos: CambioPreferenciasPorDefecto,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> PreferenciasPorDefecto:
    """Cambia el comportamiento por defecto de las respuestas. Aplica a quien no tiene
    preferencia propia.
    """
    return preferencias.cambiar_por_defecto(db, actual, datos)


@router.get("/permisos-consulta", response_model=PermisosTiposConsulta)
def ver_permisos_de_consulta(db: Session = Depends(get_db)) -> PermisosTiposConsulta:
    """Tipos de consulta que puede hacer cada rol."""
    return permisos.ver(db)


@router.put("/permisos-consulta", response_model=PermisosTiposConsulta)
def cambiar_permisos_de_consulta(
    datos: CambioPermisos,
    actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> PermisosTiposConsulta:
    """Define los tipos de consulta de los roles enviados. Aplica desde la siguiente consulta
    y queda en la auditoría.
    """
    return permisos.cambiar(db, actual, datos)
