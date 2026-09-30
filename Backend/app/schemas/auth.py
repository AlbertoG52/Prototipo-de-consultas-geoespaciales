"""Esquemas de autenticación y de estado de la sesión."""
from pydantic import BaseModel, EmailStr, Field, field_validator

from .usuario import UsuarioOut, validar_password


class MensajeOut(BaseModel):
    mensaje: str


class VerificarCorreoRequest(BaseModel):
    """RR_00_07 — el token que llegó en el enlace del correo."""

    token: str = Field(min_length=1, max_length=255)


class ReenviarVerificacionRequest(BaseModel):
    correo: EmailStr


class RecuperarPasswordRequest(BaseModel):
    """RR_00_06 criterio 1 — se pide con el correo registrado."""

    correo: EmailStr


class RestablecerPasswordRequest(BaseModel):
    """RR_00_06 criterio 3 — el token del enlace y la contraseña nueva."""

    token: str = Field(min_length=1, max_length=255)
    password: str

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        # Mismas reglas que el registro (RR_00_03).
        return validar_password(v)


class TokenOut(BaseModel):
    """Respuesta de /auth/login y /auth/anonimo."""

    access_token: str
    token_type: str = "bearer"
    tipo: str  # "usuario" | "anonimo"


class RegistroOut(BaseModel):
    mensaje: str
    usuario: UsuarioOut


class SesionOut(BaseModel):
    """Estado de la sesión actual, sea de un usuario o de un visitante.

    El frontend lo usa para decidir qué mostrar en la barra lateral: un
    visitante no ve historial ni perfil, y su contador de consultas es menor
    (RR_00_11).
    """

    tipo: str
    usuario: UsuarioOut | None = None
    limite_consultas: int
    consultas_realizadas: int
    consultas_restantes: int
    guarda_historial: bool
    # RR_00_04: minutos sin actividad que cierran la sesión. None para el
    # visitante (no tiene nada que proteger); 0 = "Nunca".
    minutos_inactividad: int | None = None
