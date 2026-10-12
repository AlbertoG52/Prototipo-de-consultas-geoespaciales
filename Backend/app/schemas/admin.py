"""Esquemas de administración — RR_00_09 y RR_57."""

from datetime import datetime

from pydantic import BaseModel

from ..dominio import EstadoCuenta, NombreRol, ResultadoConsulta, TipoSesion
from .base import EsquemaSalida


class CambioEstado(BaseModel):
    estado: EstadoCuenta


class CambioRol(BaseModel):
    rol: NombreRol


class RegistroAuditoria(EsquemaSalida):
    id: int
    accion: str
    detalle: str | None
    fecha: datetime
    afectado: str | None
    # None = el cambio se hizo desde el servidor, no desde la aplicación.
    actor: str | None


# --- RR_57: tiempos de respuesta ------------------------------------------------


class RegistroTiempo(EsquemaSalida):
    """El tiempo de una consulta (tabla 015)."""

    id: int
    registrada_en: datetime
    duracion_ms: int
    resultado: ResultadoConsulta
    tipo_sesion: TipoSesion
    especie_id: str | None
    consulta_id: int | None  # solo de cuentas registradas
    lenta: bool  # duracion_ms >= umbral_lenta_ms


class ResumenTiempos(EsquemaSalida):
    """GET /admin/tiempos: resumen del periodo y las consultas más recientes."""

    dias: int
    umbral_lenta_ms: int
    total: int
    lentas: int
    promedio_ms: int | None  # None si no hubo consultas en el periodo
    p95_ms: int | None  # el 95 % de las consultas tardó esto o menos
    maximo_ms: int | None
    registros: list[RegistroTiempo]
