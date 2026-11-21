"""Registro del tiempo de respuesta de cada consulta.

El servicio de consultas envuelve todo el procesamiento:

    with medir_consulta(identidad) as medicion:
        salida = ...
        medicion.terminar(salida)

Al salir del bloque, termine bien o con error, se guarda una fila en 'tiempos_respuesta'
con la duración, el resultado y la intención, y se escribe en el log. Las que pasan de
SEGUNDOS_RESPUESTA_LENTA quedan como WARNING y se pueden filtrar en GET /admin/tiempos. El
tiempo va desde que la consulta llega al backend hasta que la respuesta está lista.

Se guarda con una sesión de BD propia, para que quede aunque la consulta falle. Si guardar
falla, se anota en el log y la consulta sigue.

La intención se fija antes de procesar, a partir del texto, y `terminar` la precisa con lo
que se respondió.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import ColumnElement, func
from sqlalchemy.orm import Session

from .. import config
from ..db import SessionLocal
from ..dominio import IntencionConsulta, MotivoOrientacion, ResultadoConsulta
from ..errores import ErrorDominio, LimiteAlcanzado, TiempoAgotado
from ..models import TiempoRespuesta
from ..schemas.admin import ConteoIntencion, RegistroTiempo, ResumenTiempos
from ..schemas.consulta import ConsultaOut
from ..security import Identidad
from ..tiempo import ahora

logger = logging.getLogger("uvicorn.error")


@dataclass
class Medicion:
    """Lo que se sabe de la consulta al terminar; lo completa `terminar`."""

    resultado: ResultadoConsulta = ResultadoConsulta.ERROR
    especie_id: str | None = None
    consulta_id: int | None = None
    intencion: IntencionConsulta | None = None

    def terminar(self, salida: ConsultaOut) -> None:
        self.resultado = ResultadoConsulta(salida.estado)
        self.especie_id = salida.respuesta.especie.id if salida.respuesta else None
        self.consulta_id = salida.id
        # Lo que se respondió manda sobre lo que se dedujo del texto. De una consulta no
        # permitida queda el tipo que se pidió.
        if salida.motivo is MotivoOrientacion.TIPO_NO_PERMITIDO:
            return
        if salida.motivo is not None:
            self.intencion = IntencionConsulta(salida.motivo)
        elif salida.respuesta is not None:
            self.intencion = IntencionConsulta(salida.respuesta.tipo)


@contextmanager
def medir_consulta(identidad: Identidad) -> Iterator[Medicion]:
    """Mide lo que corre dentro del bloque y lo registra al salir."""
    medicion = Medicion()
    inicio = time.perf_counter()
    try:
        yield medicion
    except Exception as error:
        medicion.resultado = _resultado_de(error)
        raise
    finally:
        duracion_ms = round((time.perf_counter() - inicio) * 1000)
        _registrar(medicion, identidad, duracion_ms)


def umbral_lenta_ms() -> int:
    """Milisegundos a partir de los cuales una consulta es lenta."""
    return round(config.SEGUNDOS_RESPUESTA_LENTA * 1000)


def resumen(db: Session, dias: int, solo_lentas: bool, limite: int) -> ResumenTiempos:
    """Tiempos de los últimos `dias` días. Las cifras resumen todo el periodo; `registros`
    trae las `limite` más recientes (solo las lentas si `solo_lentas`).
    """
    umbral_ms = umbral_lenta_ms()
    desde = ahora() - timedelta(days=dias)
    en_periodo = TiempoRespuesta.registrada_en >= desde
    duracion = TiempoRespuesta.duracion_ms

    total, lentas, promedio, p95, maximo = (
        db.query(
            func.count(),
            func.count().filter(duracion >= umbral_ms),
            func.avg(duracion),
            func.percentile_cont(0.95).within_group(duracion),
            func.max(duracion),
        )
        .filter(en_periodo)
        .one()
    )

    consulta = db.query(TiempoRespuesta).filter(en_periodo)
    if solo_lentas:
        consulta = consulta.filter(duracion >= umbral_ms)
    filas = consulta.order_by(TiempoRespuesta.id.desc()).limit(limite).all()

    return ResumenTiempos(
        dias=dias,
        umbral_lenta_ms=umbral_ms,
        total=total,
        lentas=lentas,
        promedio_ms=_entero(promedio),
        p95_ms=_entero(p95),
        maximo_ms=maximo,
        por_intencion=_por_intencion(db, en_periodo),
        registros=[
            RegistroTiempo(
                id=f.id,
                registrada_en=f.registrada_en,
                duracion_ms=f.duracion_ms,
                resultado=ResultadoConsulta(f.resultado),
                tipo_sesion=f.tipo_sesion,
                especie_id=f.especie_id,
                consulta_id=f.consulta_id,
                intencion=IntencionConsulta(f.intencion) if f.intencion else None,
                lenta=f.duracion_ms >= umbral_ms,
            )
            for f in filas
        ],
    )


def _por_intencion(db: Session, en_periodo: ColumnElement[bool]) -> list[ConteoIntencion]:
    """Cuántas consultas hubo de cada intención, la más común primero. Las registradas antes
    de guardar la intención cuentan como None.
    """
    conteos = (
        db.query(TiempoRespuesta.intencion, func.count())
        .filter(en_periodo)
        .group_by(TiempoRespuesta.intencion)
        .tuples()
        .all()
    )
    return [
        ConteoIntencion(intencion=IntencionConsulta(i) if i else None, total=n)
        for i, n in sorted(conteos, key=lambda c: (-c[1], c[0] or ""))
    ]


def _entero(valor: object) -> int | None:
    return None if valor is None else round(float(valor))  # type: ignore[arg-type]


def _resultado_de(error: Exception) -> ResultadoConsulta:
    if isinstance(error, TiempoAgotado):
        return ResultadoConsulta.TIEMPO_AGOTADO
    if isinstance(error, LimiteAlcanzado):
        return ResultadoConsulta.LIMITE_ALCANZADO
    if isinstance(error, ErrorDominio):
        return ResultadoConsulta.RECHAZADA
    return ResultadoConsulta.ERROR


def _registrar(medicion: Medicion, identidad: Identidad, duracion_ms: int) -> None:
    if duracion_ms >= umbral_lenta_ms():
        logger.warning(
            "RR_57: consulta lenta, %d ms (umbral %g s), resultado=%s, especie=%s",
            duracion_ms,
            config.SEGUNDOS_RESPUESTA_LENTA,
            medicion.resultado,
            medicion.especie_id,
        )
    else:
        logger.info(
            "RR_57: consulta en %d ms, resultado=%s, intencion=%s",
            duracion_ms,
            medicion.resultado,
            medicion.intencion,
        )

    try:
        with SessionLocal() as db:
            db.add(
                TiempoRespuesta(
                    duracion_ms=duracion_ms,
                    resultado=medicion.resultado,
                    tipo_sesion=identidad.tipo,
                    especie_id=medicion.especie_id,
                    consulta_id=medicion.consulta_id,
                    intencion=medicion.intencion,
                )
            )
            db.commit()
    except Exception:
        logger.exception("RR_57: no se pudo guardar el tiempo de respuesta")
