"""Esquemas de las estadísticas de uso del sistema — RR_78."""

from datetime import date, datetime

from ..dominio import GrupoDeUso, PeriodoEstadisticas, TipoPregunta
from .base import EsquemaSalida


class ConsultasDeGrupo(EsquemaSalida):
    """Criterio 2: las consultas de un grupo (rol de hoy o visitante)."""

    grupo: GrupoDeUso
    consultas: int
    resueltas: int


class ConsultasDelDia(EsquemaSalida):
    fecha: date  # día en UTC
    consultas: int


class ConsultasDeTipo(EsquemaSalida):
    tipo: TipoPregunta
    consultas: int


class EstadisticasUso(EsquemaSalida):
    """GET /admin/estadisticas: el uso del sistema en un periodo.

    Las cifras se calculan en cada petición, así que traen las consultas
    nuevas (criterio 3).
    """

    periodo: PeriodoEstadisticas
    desde: datetime | None  # None: desde el inicio (periodo "todo")
    total: int  # criterio 1
    resueltas: int
    tasa_exito: float | None  # resueltas / total, entre 0 y 1; None sin consultas
    por_grupo: list[ConsultasDeGrupo]  # criterio 2; todos los grupos, en orden
    por_dia: list[ConsultasDelDia]  # los últimos 7 días, del más antiguo a hoy
    por_tipo: list[ConsultasDeTipo]  # tipo de pregunta (RR_29), del periodo
    generado_en: datetime


class ResumenUso(EsquemaSalida):
    """GET /admin/estadisticas/resumen: las cifras de las tarjetas del panel."""

    usuarios: int  # cuentas registradas
    usuarios_nuevos_30_dias: int
    consultas_hoy: int
    consultas_ayer: int
    consultas_30_dias: int
    tasa_exito_30_dias: float | None  # None sin consultas en el periodo
