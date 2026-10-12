"""Modelos ORM del backend.

Este paquete necesita exportar explícitamente las clases para que otros módulos
puedan importar patrones como "from ..models import Rol, Usuario".
"""

from .consulta import Consulta
from .consumo_anonimo import ConsumoAnonimo
from .conversacion import Conversacion
from .rol import Rol
from .tiempo_respuesta import TiempoRespuesta
from .token import Token
from .usuario import Usuario

__all__ = [
    "Consulta",
    "ConsumoAnonimo",
    "Conversacion",
    "Rol",
    "TiempoRespuesta",
    "Token",
    "Usuario",
]
