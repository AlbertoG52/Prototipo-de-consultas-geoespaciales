"""Conteo de consultas y límite por periodo — RR_62, RR_64, RR_65, RR_66 y RR_00_11.

Cada rol tiene un límite de consultas (`roles.limite_consultas`) y un periodo
(`roles.periodo_consultas`: día, semana o mes) que el supermoderador configura
(RR_63, services/admin.py). El visitante sin cuenta tiene
LIMITE_CONSULTAS_ANONIMO por día (RR_00_11).

RR_64 — restablecimiento periódico. El contador no se guarda ni se reinicia con
un proceso: se cuentan las consultas resueltas desde que empezó el periodo
actual. Al empezar el siguiente, la cuenta vuelve a 0 sola y la persona puede
seguir consultando. Los periodos empiezan a las 00:00 de Costa Rica (el lunes,
para la semana; el día 1, para el mes), no a la medianoche UTC, que en Costa
Rica son las 6 de la tarde.

La columna `usuarios.consultas_realizadas` (002) no se usa: contar las filas es
siempre correcto, aunque cambie el periodo o el límite a mitad de uno.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import LIMITE_CONSULTAS_ANONIMO
from ..dominio import EstadoConsulta, PeriodoConsultas
from ..models import Consulta, ConsumoAnonimo
from ..security import Identidad
from ..tiempo import HORA_COSTA_RICA, ahora

# RR_62 criterio 3: para comparar límites con periodos distintos (20 por día
# contra 100 por semana) se llevan a consultas por día. El mes cuenta como 30.
DIAS_DEL_PERIODO = {
    PeriodoConsultas.DIA: 1,
    PeriodoConsultas.SEMANA: 7,
    PeriodoConsultas.MES: 30,
}

# Cómo se nombra cada periodo en los mensajes al usuario.
POR_PERIODO = {
    PeriodoConsultas.DIA: "por día",
    PeriodoConsultas.SEMANA: "por semana",
    PeriodoConsultas.MES: "por mes",
}


@dataclass(frozen=True)
class Cupo:
    """Cuántas consultas tiene una identidad en el periodo actual y cuándo se restablecen."""

    limite: int
    periodo: PeriodoConsultas
    usadas: int
    se_restablece_en: datetime  # inicio del siguiente periodo (RR_65 criterio 2)

    @property
    def restantes(self) -> int:
        return max(self.limite - self.usadas, 0)


# --- límite y periodo de cada identidad ---------------------------------------------


def limite_de(identidad: Identidad) -> int:
    """Cuántas consultas por periodo le corresponden a esta identidad (RR_62)."""
    if identidad.usuario is not None and identidad.usuario.rol is not None:
        return identidad.usuario.rol.limite_consultas
    return LIMITE_CONSULTAS_ANONIMO


def periodo_de(identidad: Identidad) -> PeriodoConsultas:
    """Cada cuánto se restablece su contador (RR_64). El visitante, cada día."""
    if identidad.usuario is not None and identidad.usuario.rol is not None:
        return PeriodoConsultas(identidad.usuario.rol.periodo_consultas)
    return PeriodoConsultas.DIA


def consultas_por_dia(limite: int, periodo: PeriodoConsultas) -> float:
    """RR_62 criterio 3: el límite llevado a consultas por día, para compararlo."""
    return limite / DIAS_DEL_PERIODO[periodo]


# --- periodos (RR_64) ------------------------------------------------------------------


def inicio_del_periodo(periodo: PeriodoConsultas, momento: datetime | None = None) -> datetime:
    """Las 00:00 de Costa Rica del día, del lunes o del día 1 en que cae `momento`."""
    local = (momento or ahora()).astimezone(HORA_COSTA_RICA)
    dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo is PeriodoConsultas.SEMANA:
        return dia - timedelta(days=dia.weekday())
    if periodo is PeriodoConsultas.MES:
        return dia.replace(day=1)
    return dia


def fin_del_periodo(periodo: PeriodoConsultas, momento: datetime | None = None) -> datetime:
    """Cuándo empieza el periodo siguiente: ahí se restablece el contador."""
    inicio = inicio_del_periodo(periodo, momento)
    if periodo is PeriodoConsultas.SEMANA:
        return inicio + timedelta(days=7)
    if periodo is PeriodoConsultas.MES:
        siguiente = inicio.replace(day=28) + timedelta(days=4)  # siempre cae en el mes siguiente
        return siguiente.replace(day=1)
    return inicio + timedelta(days=1)


def _hoy_en_costa_rica(momento: datetime | None = None) -> date:
    return (momento or ahora()).astimezone(HORA_COSTA_RICA).date()


# --- conteo -----------------------------------------------------------------------------


def consultas_del_periodo(
    db: Session, identidad: Identidad, momento: datetime | None = None
) -> int:
    """Cuántas consultas lleva esta identidad en el periodo actual.

    Del usuario registrado se cuentan solo las consultas resueltas, por el
    momento en que se resolvieron: las ambiguas y las sin coincidencias también
    se guardan (tabla 012) pero no cuestan, y una ambigua de un periodo
    anterior que se resuelve hoy cuenta en este.
    """
    if identidad.usuario is not None:
        inicio = inicio_del_periodo(periodo_de(identidad), momento)
        return (
            db.query(func.count(Consulta.id))
            .filter(
                Consulta.usuario_id == identidad.usuario.id,
                Consulta.estado == EstadoConsulta.RESUELTA,
                Consulta.resuelta_en >= inicio,
            )
            .scalar()
            or 0
        )

    if not identidad.anon_id:
        return 0

    fila = (
        db.query(ConsumoAnonimo)
        .filter(
            ConsumoAnonimo.anon_id == identidad.anon_id,
            ConsumoAnonimo.fecha == _hoy_en_costa_rica(momento),
        )
        .first()
    )
    return fila.consultas_realizadas if fila else 0


def cupo_de(db: Session, identidad: Identidad, momento: datetime | None = None) -> Cupo:
    """Límite, periodo, consultas usadas y cuándo se restablecen (RR_65, RR_66)."""
    periodo = periodo_de(identidad)
    return Cupo(
        limite=limite_de(identidad),
        periodo=periodo,
        usadas=consultas_del_periodo(db, identidad, momento),
        se_restablece_en=fin_del_periodo(periodo, momento),
    )


def registrar_consumo_anonimo(db: Session, anon_id: str) -> None:
    """Suma una consulta al contador diario del visitante.

    Guarda solo el número, nunca el texto de la consulta (RR_00_11 criterio 1).
    El día es el de Costa Rica, igual que el de los usuarios registrados.
    """
    hoy = _hoy_en_costa_rica()
    fila = (
        db.query(ConsumoAnonimo)
        .filter(ConsumoAnonimo.anon_id == anon_id, ConsumoAnonimo.fecha == hoy)
        .first()
    )
    if fila is None:
        fila = ConsumoAnonimo(anon_id=anon_id, fecha=hoy, consultas_realizadas=1)
        db.add(fila)
    else:
        fila.consultas_realizadas += 1
    db.commit()
