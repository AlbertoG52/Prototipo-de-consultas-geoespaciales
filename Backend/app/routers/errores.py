"""Traducción de los errores de negocio (app/errores.py) a respuestas HTTP."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from ..errores import ErrorDominio


@contextmanager
def errores_http() -> Iterator[None]:
    """Convierte un ErrorDominio lanzado por un servicio en HTTPException.

    Uso en un endpoint:

        with errores_http():
            return servicio.hacer_algo(...)
    """
    try:
        yield
    except ErrorDominio as error:
        raise HTTPException(status_code=error.estado_http, detail=error.detalle) from error
