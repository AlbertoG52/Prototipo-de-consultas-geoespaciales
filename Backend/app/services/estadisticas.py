"""Estadísticas de uso del sistema — RR_78.

- Criterio 1: el supermoderador ve el total de consultas realizadas.
- Criterio 2: agrupadas por rol. Cada cuenta cuenta con el rol que tiene hoy,
  como el uso por rol de RR_76 (services/admin.py); el visitante sin cuenta es
  un grupo aparte (dominio.GrupoDeUso).
- Criterio 3: no hay nada precalculado: cada petición cuenta lo que hay en la
  BD, así que trae las consultas nuevas. El panel vuelve a pedirlas cada 30 s.

Qué es una consulta realizada (misma regla que RR_76):

    cuentas      filas de 'consultas' (012) que no son orientaciones: resueltas,
                 ambiguas y sin coincidencias. Una ambigua es una sola fila,
                 aunque se resuelva después. Fecha: cuándo se hizo.
    visitantes   del visitante no se guardan consultas (RR_00_11): se cuentan
                 sus filas de 'tiempos_respuesta' (015) resueltas o sin
                 coincidencias. Una ambigua y la especie que elige quedan como
                 dos filas, así que cuenta cuando se resuelve. Solo hay datos
                 desde la tabla 015.

El tipo de pregunta (RR_29) sale de la intención registrada en
'tiempos_respuesta' (017, RR_33), con la misma regla que los visitantes.

Los días son en UTC, como el límite diario (services/uso.py).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import ColumnElement, func
from sqlalchemy.orm import InstrumentedAttribute, Session

from ..dominio import (
    EstadoConsulta,
    GrupoDeUso,
    PeriodoEstadisticas,
    ResultadoConsulta,
    TipoPregunta,
    TipoSesion,
)
from ..models import Consulta, Rol, TiempoRespuesta, Usuario
from ..schemas.estadisticas import (
    ConsultasDeGrupo,
    ConsultasDelDia,
    ConsultasDeTipo,
    EstadisticasUso,
    ResumenUso,
)
from ..tiempo import ahora

# Resultados de 'tiempos_respuesta' que cuentan como consulta (ver el módulo).
RESULTADOS_CONTADOS = (ResultadoConsulta.RESUELTA, ResultadoConsulta.SIN_COINCIDENCIAS)

# Días del gráfico de consultas por día, contando hoy.
DIAS_DEL_GRAFICO = 7

# Días hacia atrás (sin contar hoy) donde empieza cada periodo; None = sin límite.
_DIAS_ATRAS = {
    PeriodoEstadisticas.HOY: 0,
    PeriodoEstadisticas.ULTIMOS_7_DIAS: 6,
    PeriodoEstadisticas.ULTIMOS_30_DIAS: 29,
    PeriodoEstadisticas.TODO: None,
}


@dataclass(frozen=True)
class Conteo:
    consultas: int = 0
    resueltas: int = 0

    def __add__(self, otro: Conteo) -> Conteo:
        return Conteo(self.consultas + otro.consultas, self.resueltas + otro.resueltas)

    @property
    def tasa_exito(self) -> float | None:
        """Resueltas / consultas, entre 0 y 1; None si no hubo consultas."""
        return self.resueltas / self.consultas if self.consultas else None


def inicio_del_dia(dias_atras: int = 0) -> datetime:
    """Medianoche UTC de hoy, o de `dias_atras` días antes."""
    dia = ahora().date() - timedelta(days=dias_atras)
    return datetime.combine(dia, time.min, tzinfo=UTC)


def desde_de(periodo: PeriodoEstadisticas) -> datetime | None:
    """Desde cuándo cuenta el periodo; None para "todo"."""
    dias = _DIAS_ATRAS[periodo]
    return None if dias is None else inicio_del_dia(dias)


# --- lo que piden los endpoints ----------------------------------------------------


def estadisticas(db: Session, periodo: PeriodoEstadisticas) -> EstadisticasUso:
    """Criterios 1, 2 y 3: el uso del sistema en el periodo, calculado ahora."""
    desde = desde_de(periodo)
    grupos = por_grupo(db, desde)
    total = sum(grupos.values(), Conteo())
    return EstadisticasUso(
        periodo=periodo,
        desde=desde,
        total=total.consultas,
        resueltas=total.resueltas,
        tasa_exito=total.tasa_exito,
        por_grupo=[
            ConsultasDeGrupo(grupo=g, consultas=c.consultas, resueltas=c.resueltas)
            for g, c in grupos.items()
        ],
        por_dia=_por_dia(db),
        por_tipo=_por_tipo(db, desde),
        generado_en=ahora(),
    )


def resumen(db: Session) -> ResumenUso:
    """Las cifras de las tarjetas del panel: cuentas, hoy, ayer y últimos 30 días."""
    hoy, hace_30 = inicio_del_dia(), inicio_del_dia(29)
    ultimos_30 = _total(db, hace_30)
    usuarios, nuevos = (
        db.query(
            func.count(Usuario.id), func.count(Usuario.id).filter(Usuario.creado_en >= hace_30)
        )
        .tuples()
        .one()
    )
    return ResumenUso(
        usuarios=usuarios,
        usuarios_nuevos_30_dias=nuevos,
        consultas_hoy=_total(db, hoy).consultas,
        consultas_ayer=_total(db, inicio_del_dia(1), hasta=hoy).consultas,
        consultas_30_dias=ultimos_30.consultas,
        tasa_exito_30_dias=ultimos_30.tasa_exito,
    )


# --- conteos -------------------------------------------------------------------------


def por_grupo(
    db: Session, desde: datetime | None, hasta: datetime | None = None
) -> dict[GrupoDeUso, Conteo]:
    """Criterio 2: el conteo de cada grupo entre `desde` y `hasta`, con ceros."""
    conteos = dict.fromkeys(GrupoDeUso, Conteo())
    for rol, conteo in _de_cuentas(db, desde, hasta):
        conteos[GrupoDeUso(rol)] = conteo
    conteos[GrupoDeUso.VISITANTE] = _de_visitantes(db, desde, hasta)
    return conteos


def _total(db: Session, desde: datetime | None, hasta: datetime | None = None) -> Conteo:
    return sum(por_grupo(db, desde, hasta).values(), Conteo())


def _de_cuentas(
    db: Session, desde: datetime | None, hasta: datetime | None
) -> Iterable[tuple[str, Conteo]]:
    """Las consultas guardadas de las cuentas, por el rol que tienen hoy."""
    filas = (
        db.query(
            Rol.nombre,
            func.count(Consulta.id),
            func.count(Consulta.id).filter(Consulta.estado == EstadoConsulta.RESUELTA),
        )
        .join(Usuario, Usuario.rol_id == Rol.id)
        .join(Consulta, Consulta.usuario_id == Usuario.id)
        .filter(_es_de_cuenta(), *_entre(Consulta.realizada_en, desde, hasta))
        .group_by(Rol.nombre)
        .tuples()
        .all()
    )
    return [(rol, Conteo(consultas, resueltas)) for rol, consultas, resueltas in filas]


def _de_visitantes(db: Session, desde: datetime | None, hasta: datetime | None) -> Conteo:
    consultas, resueltas = (
        db.query(
            func.count(TiempoRespuesta.id),
            func.count(TiempoRespuesta.id).filter(
                TiempoRespuesta.resultado == ResultadoConsulta.RESUELTA
            ),
        )
        .filter(_es_de_visitante(), *_entre(TiempoRespuesta.registrada_en, desde, hasta))
        .tuples()
        .one()
    )
    return Conteo(consultas, resueltas)


def _por_dia(db: Session) -> list[ConsultasDelDia]:
    """Las consultas de cada uno de los últimos DIAS_DEL_GRAFICO días, con ceros."""
    desde = inicio_del_dia(DIAS_DEL_GRAFICO - 1)
    por_fecha: dict[date, int] = {
        (desde + timedelta(days=d)).date(): 0 for d in range(DIAS_DEL_GRAFICO)
    }
    for columna, condicion in (
        (Consulta.realizada_en, _es_de_cuenta()),
        (TiempoRespuesta.registrada_en, _es_de_visitante()),
    ):
        dia = func.date(columna)
        filas = db.query(dia, func.count()).filter(condicion, columna >= desde).group_by(dia)
        for fecha, consultas in filas.tuples():
            por_fecha[fecha] = por_fecha.get(fecha, 0) + consultas
    return [ConsultasDelDia(fecha=f, consultas=n) for f, n in sorted(por_fecha.items())]


def _por_tipo(db: Session, desde: datetime | None) -> list[ConsultasDeTipo]:
    """Cuántas consultas hubo de cada tipo de pregunta (RR_29), con ceros."""
    filas = (
        db.query(TiempoRespuesta.intencion, func.count(TiempoRespuesta.id))
        .filter(
            TiempoRespuesta.resultado.in_(RESULTADOS_CONTADOS),
            TiempoRespuesta.intencion.in_(list(TipoPregunta)),
            *_entre(TiempoRespuesta.registrada_en, desde, None),
        )
        .group_by(TiempoRespuesta.intencion)
        .tuples()
        .all()
    )
    conteos = dict(filas)
    return [ConsultasDeTipo(tipo=t, consultas=conteos.get(t, 0)) for t in TipoPregunta]


def _es_de_cuenta() -> ColumnElement[bool]:
    return Consulta.estado != EstadoConsulta.ORIENTACION


def _es_de_visitante() -> ColumnElement[bool]:
    return (TiempoRespuesta.tipo_sesion == TipoSesion.ANONIMO) & TiempoRespuesta.resultado.in_(
        RESULTADOS_CONTADOS
    )


def _entre(
    columna: InstrumentedAttribute[datetime], desde: datetime | None, hasta: datetime | None
) -> list[ColumnElement[bool]]:
    """Las condiciones de fecha: desde `desde` (incluido) hasta `hasta` (excluido)."""
    condiciones = []
    if desde is not None:
        condiciones.append(columna >= desde)
    if hasta is not None:
        condiciones.append(columna < hasta)
    return condiciones
