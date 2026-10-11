"""Esquemas de la página de perfil: nombre, contraseña e inactividad de la sesión.

El nombre y la contraseña usan las mismas reglas que el registro
(schemas/usuario.py); para la contraseña es lo que pide el criterio 3 de RR_00_03.
"""

from pydantic import BaseModel, Field, field_validator

from ..config import OPCIONES_INACTIVIDAD
from .usuario import LONGITUD_MAXIMA_NOMBRE, validar_nombre, validar_password


class CambioNombreRequest(BaseModel):
    nombre: str = Field(max_length=LONGITUD_MAXIMA_NOMBRE)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        return validar_nombre(v)


class CambioPasswordRequest(BaseModel):
    # La actual no se valida con las reglas: puede ser de antes de que existieran.
    password_actual: str = Field(min_length=1)
    password_nueva: str

    @field_validator("password_nueva")
    @classmethod
    def _nueva(cls, v: str) -> str:
        return validar_password(v)


class CambioInactividadRequest(BaseModel):
    """RR_00_04 criterio 2 — el periodo de inactividad es configurable.

    Solo se aceptan las opciones que ofrece el perfil; 0 significa "Nunca".
    """

    minutos: int

    @field_validator("minutos")
    @classmethod
    def _minutos(cls, v: int) -> int:
        if v not in OPCIONES_INACTIVIDAD:
            raise ValueError("Elige una de las opciones de tiempo de inactividad disponibles.")
        return v
