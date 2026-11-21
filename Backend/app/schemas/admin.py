"""Esquemas de administración: roles, auditoría, tiempos de respuesta e historial de uso."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ..dominio import (
    EstadoConsulta,
    EstadoCuenta,
    IntencionConsulta,
    NombreRol,
    PeriodoConsultas,
    ResultadoConsulta,
    TipoSesion,
)
from .base import EsquemaSalida
from .usuario import UsuarioOut


class CambioEstado(BaseModel):
    estado: EstadoCuenta


class CambioRol(BaseModel):
    rol: NombreRol


# --- límite de consultas por rol -------------------------------------------------

# Los mismos de la restricción de la tabla 'roles'.
LIMITE_MINIMO_CONSULTAS = 1
LIMITE_MAXIMO_CONSULTAS = 100_000


class RolOut(EsquemaSalida):
    """Un rol con su límite de consultas y su periodo."""

    nombre: NombreRol
    descripcion: str | None
    limite_consultas: int
    periodo_consultas: PeriodoConsultas


class CambioLimite(BaseModel):
    """PATCH /admin/roles/{rol}: el nuevo límite y su periodo."""

    limite_consultas: int
    periodo_consultas: PeriodoConsultas

    @field_validator("limite_consultas", mode="before")
    @classmethod
    def _numero_valido(cls, v: object) -> object:
        # Mensaje en español para el frontend. bool es un int en Python: true no es un
        # número de consultas.
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("El límite debe ser un número entero de consultas.")
        if not LIMITE_MINIMO_CONSULTAS <= v <= LIMITE_MAXIMO_CONSULTAS:
            raise ValueError(
                f"El límite debe estar entre {LIMITE_MINIMO_CONSULTAS} y "
                f"{LIMITE_MAXIMO_CONSULTAS:,}".replace(",", " ")
                + " consultas."
            )
        return v


class RegistroAuditoria(EsquemaSalida):
    id: int
    accion: str
    detalle: str | None
    fecha: datetime
    afectado: str | None
    # None = el cambio se hizo desde el servidor, no desde la aplicación.
    actor: str | None


# --- tiempos de respuesta --------------------------------------------------------


class RegistroTiempo(EsquemaSalida):
    """Tiempo de una consulta y su intención. `id` identifica el registro, también para los
    visitantes.
    """

    id: int
    registrada_en: datetime
    duracion_ms: int
    resultado: ResultadoConsulta
    tipo_sesion: TipoSesion
    especie_id: str | None
    consulta_id: int | None  # solo de cuentas registradas
    intencion: IntencionConsulta | None = None  # None: registrada antes de guardar la intención
    lenta: bool  # duracion_ms >= umbral_lenta_ms


class ConteoIntencion(EsquemaSalida):
    """Cuántas consultas del periodo tuvieron una intención."""

    intencion: IntencionConsulta | None  # None: registradas antes de guardar la intención
    total: int


class ResumenTiempos(EsquemaSalida):
    """GET /admin/tiempos: resumen del periodo y las consultas más recientes."""

    dias: int
    umbral_lenta_ms: int
    total: int
    lentas: int
    promedio_ms: int | None  # None si no hubo consultas en el periodo
    p95_ms: int | None  # el 95 % de las consultas tardó esto o menos
    maximo_ms: int | None
    # Cuántas consultas hubo de cada intención en el periodo.
    por_intencion: list[ConteoIntencion] = Field(default_factory=list)
    registros: list[RegistroTiempo]


# --- historial de uso -------------------------------------------------------------


class ConsultaDeUsuario(EsquemaSalida):
    """Una consulta del historial de uso de una cuenta."""

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
    """GET /admin/uso-por-rol: cuentas de un rol y sus consultas guardadas."""

    rol: NombreRol
    usuarios: int  # cuentas que tienen hoy ese rol
    consultas: int  # consultas guardadas de esas cuentas
