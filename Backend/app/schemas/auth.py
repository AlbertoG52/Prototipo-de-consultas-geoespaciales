"""Esquemas de autenticación y de estado de la sesión."""

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..dominio import TipoSesion
from .base import EsquemaSalida
from .usuario import UsuarioOut, validar_password


class MensajeOut(EsquemaSalida):
    mensaje: str


class VerificarCorreoRequest(BaseModel):
    """RR_00_07 — el token que llegó en el enlace del correo."""

    token: str = Field(min_length=1, max_length=255)


class CorreoRequest(BaseModel):
    """Solo el correo: para reenviar la verificación (RR_00_07) y para pedir la
    recuperación de contraseña con el correo registrado (RR_00_06 criterio 1)."""

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


class TokenOut(EsquemaSalida):
    """Respuesta de /auth/login y /auth/anonimo."""

    access_token: str
    token_type: str = "bearer"
    tipo: TipoSesion


class RegistroOut(EsquemaSalida):
    mensaje: str
    usuario: UsuarioOut


class SesionOut(EsquemaSalida):
    """Estado de la sesión actual, sea de un usuario o de un visitante.

    El frontend lo usa para decidir qué mostrar en la barra lateral: un
    visitante no ve historial ni perfil, y su contador de consultas es menor
    (RR_00_11).
    """

    tipo: TipoSesion
    usuario: UsuarioOut | None = None
    limite_consultas: int
    consultas_realizadas: int
    consultas_restantes: int
    guarda_historial: bool
    # RR_00_04: minutos sin actividad que cierran la sesión. None para el
    # visitante (no tiene nada que proteger); 0 = "Nunca".
    minutos_inactividad: int | None = None
    # RR_38: tiempo máximo de una consulta. El frontend deja de esperar un poco
    # después, por si el servidor no llega a responder.
    segundos_maximos_consulta: float
