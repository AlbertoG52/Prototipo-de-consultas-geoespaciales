"""Hora actual y tiempo máximo de una operación.

Todo el backend compara fechas con columnas `timestamptz`, así que usa `ahora()`
en lugar de `datetime.now()` (que sin zona horaria devuelve la hora local del
servidor y no se puede comparar con las de la base de datos).

RR_38 — tiempo máximo de una consulta. El servicio de consultas abre un plazo:

    with plazo(config.SEGUNDOS_MAXIMOS_CONSULTA):
        ...

Dentro del bloque, `verificar_plazo()` lanza `TiempoAgotado` si el tiempo ya se
acabó, y `segundos_restantes()` dice cuánto queda. El adaptador MCP lo usa para
que una llamada a CR-BioLM nunca dure más de lo que le queda a la consulta, y
`alcanza_para_esperar()` evita esperar un reintento que ya no cabe. El
plazo vive en una variable de contexto, así que no hay que pasarlo de función
en función, y cada petición tiene el suyo.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime

from .errores import TiempoAgotado


def ahora() -> datetime:
    """Momento actual con zona horaria UTC."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class _Plazo:
    segundos: float  # tiempo máximo con el que se abrió
    vence: float  # momento de vencimiento, en time.monotonic()


_plazo_actual: ContextVar[_Plazo | None] = ContextVar("plazo_actual", default=None)


@contextmanager
def plazo(segundos: float) -> Iterator[None]:
    """Fija un tiempo máximo para lo que se ejecute dentro del bloque."""
    token = _plazo_actual.set(_Plazo(segundos, time.monotonic() + segundos))
    try:
        yield
    finally:
        _plazo_actual.reset(token)


def segundos_restantes() -> float | None:
    """Segundos que le quedan al plazo abierto (negativo si venció), o None sin plazo."""
    actual = _plazo_actual.get()
    return None if actual is None else actual.vence - time.monotonic()


def verificar_plazo() -> None:
    """Lanza TiempoAgotado si el plazo abierto ya venció. Sin plazo no hace nada."""
    actual = _plazo_actual.get()
    if actual is not None and time.monotonic() >= actual.vence:
        raise TiempoAgotado(actual.segundos)


def alcanza_para_esperar(segundos: float) -> bool:
    """False si, tras esperar `segundos`, al plazo abierto ya no le quedaría tiempo.

    Sin plazo siempre alcanza. Lo usan los reintentos (MCP y RR_58) para no
    esperar un intento que de todos modos se cortaría por RR_38.
    """
    restantes = segundos_restantes()
    return restantes is None or restantes > segundos
