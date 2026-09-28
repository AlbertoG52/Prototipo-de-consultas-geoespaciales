"""Esquemas de entrada y salida de usuarios."""
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..config import LONGITUD_MAXIMA_PASSWORD, LONGITUD_MINIMA_PASSWORD
from ..sanitizacion import sanitizar_texto


def validar_password(valor: str) -> str:
    #Reglas mínimas de contraseña.
    
    if len(valor) < LONGITUD_MINIMA_PASSWORD:
        raise ValueError(f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.")
    if len(valor.encode("utf-8")) > LONGITUD_MAXIMA_PASSWORD:
        raise ValueError(f"La contraseña no puede superar los {LONGITUD_MAXIMA_PASSWORD} caracteres.")
    if not re.search(r"[A-Z]", valor):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
    if not re.search(r"\d", valor):
        raise ValueError("La contraseña debe incluir al menos un número.")
    if not re.search(r"[^A-Za-z0-9]", valor):
        raise ValueError("La contraseña debe incluir al menos un carácter especial o símbolo.")
    return valor


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    correo: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validar_password(v)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        # RR_00_08. La contraseña no pasa por aquí: sanitizarla cambiaría la
        # credencial que el usuario escribió.
        limpio = sanitizar_texto(v)
        if not limpio:
            raise ValueError("El nombre es requerido.")
        return limpio


class LoginRequest(BaseModel):
    correo: EmailStr
    password: str


class UsuarioOut(BaseModel):
    id: int
    nombre: str | None = None
    correo: str
    rol: str
    estado: str
    correo_verificado: bool

    model_config = {"from_attributes": True}
