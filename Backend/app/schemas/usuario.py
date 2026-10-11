"""Esquemas de entrada y salida de usuarios."""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..config import LONGITUD_MAXIMA_PASSWORD, LONGITUD_MINIMA_PASSWORD
from ..dominio import EstadoCuenta, NombreRol
from ..models import Usuario
from ..sanitizacion import sanitizar_texto
from .base import EsquemaSalida

LONGITUD_MINIMA_NOMBRE = 2
LONGITUD_MAXIMA_NOMBRE = 120


def validar_nombre(valor: str) -> str:
    """Regla única del nombre visible, para el registro y para el perfil.

    Se sanitiza (RR_00_08) y se colapsan espacios, tabuladores y saltos de
    línea; el largo se revisa después de limpiar, así "  a  " no es válido.
    """
    limpio = " ".join(sanitizar_texto(valor).split())
    if len(limpio) < LONGITUD_MINIMA_NOMBRE:
        raise ValueError(f"El nombre debe tener al menos {LONGITUD_MINIMA_NOMBRE} caracteres.")
    return limpio


def validar_password(valor: str) -> str:
    """Reglas mínimas de contraseña (RR_00_03), en el registro y en cada cambio."""
    if len(valor) < LONGITUD_MINIMA_PASSWORD:
        raise ValueError(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres."
        )
    if len(valor.encode("utf-8")) > LONGITUD_MAXIMA_PASSWORD:
        raise ValueError(
            f"La contraseña no puede superar los {LONGITUD_MAXIMA_PASSWORD} caracteres."
        )
    if not re.search(r"[A-Z]", valor):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
    if not re.search(r"\d", valor):
        raise ValueError("La contraseña debe incluir al menos un número.")
    if not re.search(r"[^A-Za-z0-9]", valor):
        raise ValueError("La contraseña debe incluir al menos un carácter especial o símbolo.")
    return valor


class RegistroRequest(BaseModel):
    nombre: str = Field(max_length=LONGITUD_MAXIMA_NOMBRE)
    correo: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        # No se sanitiza: cambiaría la credencial que el usuario escribió.
        return validar_password(v)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        return validar_nombre(v)


class LoginRequest(BaseModel):
    correo: EmailStr
    password: str


class UsuarioOut(EsquemaSalida):
    id: int
    nombre: str | None = None
    correo: str
    rol: NombreRol
    estado: EstadoCuenta
    correo_verificado: bool

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def de_modelo(cls, usuario: Usuario) -> "UsuarioOut":
        """Salida pública de un usuario: el rol va por nombre, no por id."""
        return cls(
            id=usuario.id,
            nombre=usuario.nombre,
            correo=usuario.correo,
            rol=usuario.rol.nombre if usuario.rol else NombreRol.USUARIO,
            estado=usuario.estado,
            correo_verificado=usuario.correo_verificado,
        )
