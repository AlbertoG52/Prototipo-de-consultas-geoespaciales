"""Esquemas de autenticación y de estado de la sesión."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..dominio import PeriodoConsultas, TipoSesion
from .base import EsquemaSalida
from .usuario import UsuarioOut, validar_password


class MensajeOut(EsquemaSalida):
    mensaje: str


class VerificarCorreoRequest(BaseModel):
    """Token que llegó en el enlace del correo."""

    token: str = Field(min_length=1, max_length=255)


class CorreoRequest(BaseModel):
    """Solo el correo: para reenviar la verificación o pedir la recuperación de contraseña."""

    correo: EmailStr


class RestablecerPasswordRequest(BaseModel):
    """Token del enlace y contraseña nueva."""

    token: str = Field(min_length=1, max_length=255)
    password: str

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        # Mismas reglas que el registro.
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
    """Estado de la sesión actual, de una cuenta o de un visitante. El frontend lo usa para
    decidir qué mostrar en la barra lateral.
    """

    tipo: TipoSesion
    usuario: UsuarioOut | None = None
    # Límite del rol, consultas hechas y restantes en el periodo actual (día, semana o
    # mes)...
    limite_consultas: int
    consultas_realizadas: int
    consultas_restantes: int
    periodo_consultas: PeriodoConsultas
    # ...y cuándo se restablece el contador.
    consultas_se_restablecen_en: datetime
    guarda_historial: bool
    # Minutos sin actividad que cierran la sesión. None para el visitante; 0 = "Nunca".
    minutos_inactividad: int | None = None
    # Tiempo máximo de una consulta. El frontend deja de esperar un poco después.
    segundos_maximos_consulta: float
    # Máximo de caracteres de una consulta; el frontend avisa antes de enviar y el servidor
    # lo vuelve a comprobar.
    longitud_maxima_consulta: int
