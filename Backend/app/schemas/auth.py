"""Esquemas de autenticación y de estado de la sesión."""
from pydantic import BaseModel

from .usuario import UsuarioOut


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
