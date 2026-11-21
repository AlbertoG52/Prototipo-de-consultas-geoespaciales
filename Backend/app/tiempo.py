"""Hora actual y tiempo máximo de una operación.

El backend compara fechas con columnas `timestamptz`, por eso usa `ahora()` (UTC) en lugar
de `datetime.now()`.

`plazo(segundos)` abre un tiempo máximo para lo que se ejecute dentro del bloque.
`verificar_plazo()` lanza `TiempoAgotado` si ya venció, `segundos_restantes()` dice cuánto
queda y `alcanza_para_esperar()` evita esperar un reintento que no cabe. El plazo vive en
una variable de contexto, así que cada petición tiene el suyo.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from .errores import TiempoAgotado

# Costa Rica no tiene horario de verano: siempre es UTC-6. Solo se usa para escribir fechas
# en textos para el usuario.
HORA_COSTA_RICA = timezone(timedelta(hours=-6), "UTC-6")


def ahora() -> datetime:
    """Momento actual con zona horaria UTC."""
    return datetime.now(UTC)


def fecha_para_mostrar(momento: datetime) -> str:
    """La fecha de `momento` en Costa Rica, como '19/10/2026', para textos al usuario."""
    return momento.astimezone(HORA_COSTA_RICA).strftime("%d/%m/%Y")


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
    """False si, tras esperar `segundos`, al plazo abierto ya no le quedaría tiempo. Sin plazo
    siempre alcanza.
    """
    restantes = segundos_restantes()
    return restantes is None or restantes > segundos
