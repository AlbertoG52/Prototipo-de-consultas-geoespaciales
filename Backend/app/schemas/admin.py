"""Esquemas de administración — RR_00_09, RR_57 y RR_76."""

from datetime import datetime

from pydantic import BaseModel

from ..dominio import EstadoConsulta, EstadoCuenta, NombreRol, ResultadoConsulta, TipoSesion
from .base import EsquemaSalida
from .usuario import UsuarioOut


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


# --- RR_76: historial de uso ---------------------------------------------------------


class ConsultaDeUsuario(EsquemaSalida):
    """Una consulta del historial de uso de un usuario (criterios 1 y 2)."""

    id: int
    # None cuando ADMIN_VE_TEXTO_CONSULTAS está apagado (config.py).
    texto: str | None
    estado: EstadoConsulta
    especie: str | None  # nombre científico, solo si se resolvió
    realizada_en: datetime


class HistorialUso(EsquemaSalida):
    """GET /admin/usuarios/{id}/consultas: las consultas de una cuenta."""

    usuario: UsuarioOut
    texto_visible: bool  # ADMIN_VE_TEXTO_CONSULTAS
    total: int  # todas sus consultas guardadas, para paginar
    consultas: list[ConsultaDeUsuario]  # de la más reciente a la más antigua


class UsoDeRol(EsquemaSalida):
    """GET /admin/uso-por-rol: el uso del sistema por las cuentas de un rol (criterio 3)."""

    rol: NombreRol
    usuarios: int  # cuentas que tienen hoy ese rol
    consultas: int  # consultas guardadas de esas cuentas
