"""Esquemas de administración — RR_00_09."""

from datetime import datetime

from pydantic import BaseModel

from ..dominio import EstadoCuenta, NombreRol
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
