"""Esquemas de administración — RR_00_09."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CambioEstado(BaseModel):
    estado: Literal["activo", "inactivo"]


class CambioRol(BaseModel):
    rol: Literal["usuario", "moderador", "supermoderador"]


class RegistroAuditoria(BaseModel):
    id: int
    accion: str
    detalle: str | None
    fecha: datetime
    afectado: str | None
    # None = el cambio se hizo desde el servidor, no desde la aplicación.
    actor: str | None
