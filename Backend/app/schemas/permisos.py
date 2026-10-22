"""Esquemas de los tipos de consulta permitidos por rol — RR_77."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..dominio import RolDeConsulta, TipoPregunta
from .base import EsquemaSalida


class PermisosDeRol(EsquemaSalida):
    """Los tipos de consulta que puede hacer un rol."""

    rol: RolDeConsulta
    permitidos: list[TipoPregunta]


class PermisosTiposConsulta(EsquemaSalida):
    """GET /admin/permisos-consulta: la configuración de todos los roles y su último cambio.

    El supermoderador no aparece: siempre puede hacer todos los tipos.
    """

    roles: list[PermisosDeRol]
    actualizado_en: datetime | None = None
    # Correo de quien hizo el último cambio; None = valor inicial.
    actualizado_por: str | None = None


class CambioPermisosDeRol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: RolDeConsulta
    # Los tipos que quedan permitidos; los demás quedan bloqueados.
    permitidos: list[TipoPregunta]


class CambioPermisos(BaseModel):
    """PUT /admin/permisos-consulta. Solo cambian los roles que vienen."""

    model_config = ConfigDict(extra="forbid")

    roles: list[CambioPermisosDeRol] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def _sin_repetir(cls, roles: list[CambioPermisosDeRol]) -> list[CambioPermisosDeRol]:
        if len({r.rol for r in roles}) != len(roles):
            raise ValueError("Cada rol puede venir una sola vez.")
        return roles
