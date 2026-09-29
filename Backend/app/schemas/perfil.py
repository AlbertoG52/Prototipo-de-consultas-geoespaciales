"""Esquemas de la página de perfil: editar el nombre y cambiar la contraseña.

Reutiliza las reglas que ya existen en vez de duplicarlas:

- validar_password (schemas/usuario.py, RR_00_03): la misma regla del registro
  se aplica al cambio de contraseña, que es lo que pide su criterio 3.
- sanitizar_texto (RR_00_08): el nombre se limpia igual que en el registro.
"""
from pydantic import BaseModel, Field, field_validator

from ..sanitizacion import sanitizar_texto
from .usuario import validar_password

LONGITUD_MINIMA_NOMBRE = 2
LONGITUD_MAXIMA_NOMBRE = 120


class CambioNombreRequest(BaseModel):
    nombre: str = Field(max_length=LONGITUD_MAXIMA_NOMBRE)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        # Además de sanitizar, se colapsan espacios, tabuladores y saltos de
        # línea: en un nombre no tienen sentido "Ana    María" ni un "\n".
        limpio = " ".join(sanitizar_texto(v).split())
        # El largo se revisa después de limpiar: "  a  " no es un nombre válido.
        if len(limpio) < LONGITUD_MINIMA_NOMBRE:
            raise ValueError(
                f"El nombre debe tener al menos {LONGITUD_MINIMA_NOMBRE} caracteres."
            )
        return limpio


class CambioPasswordRequest(BaseModel):
    # La actual no se valida con las reglas: puede ser de antes de que existieran.
    password_actual: str = Field(min_length=1)
    password_nueva: str

    @field_validator("password_nueva")
    @classmethod
    def _nueva(cls, v: str) -> str:
        return validar_password(v)
