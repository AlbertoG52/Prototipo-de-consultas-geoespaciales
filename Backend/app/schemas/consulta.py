"""Esquemas de consultas y de sus respuestas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..config import LONGITUD_MAXIMA_CONSULTA
from ..sanitizacion import sanitizar_texto

# Estados de una consulta (columna consultas.estado):
#   - "resuelta"          -> trae 'respuesta'; es la única que cuesta del límite diario
#   - "ambigua"           -> trae 'candidatos' (RR_17); sigue pendiente hasta que se elige
#   - "sin_coincidencias" -> no se reconoció ninguna especie
ESTADO_RESUELTA = "resuelta"
ESTADO_AMBIGUA = "ambigua"
ESTADO_SIN_COINCIDENCIAS = "sin_coincidencias"
EstadoConsulta = Literal["resuelta", "ambigua", "sin_coincidencias"]


class RegistroPresencia(BaseModel):
    """Un punto de presencia de la especie (RR_18, vista de lista)."""

    localidad: str
    fecha: str
    latitud: float
    longitud: float
    elevacion_m: int | None = None
    fuente: str


class EspecieCandidata(BaseModel):
    """Una de las especies que coinciden con la consulta (RR_17)."""

    id: str
    nombre_comun: str | None = None
    nombre_cientifico: str
    familia: str


class RespuestaConsulta(BaseModel):
    """Lo que el agente devuelve para una consulta ya resuelta."""

    especie: EspecieCandidata
    texto: str
    elevacion: str | None = None
    registros: list[RegistroPresencia] = Field(default_factory=list)
    total_registros: int = 0
    fuentes: list[str] = Field(default_factory=list)


class FichaEspecie(EspecieCandidata):
    """RR_20 — ficha completa de una especie.

    Los campos que el catálogo no tenga llegan como None y la ficha los
    muestra como "Sin dato" en lugar de inventarlos.
    """

    habitat: str | None = None
    elevacion: str | None = None
    descripcion: str | None = None
    registros: list[RegistroPresencia] = Field(default_factory=list)
    total_registros: int = 0
    fuentes: list[str] = Field(default_factory=list)


class ConsultaRequest(BaseModel):
    texto: str = Field(min_length=1, max_length=LONGITUD_MAXIMA_CONSULTA)

    # RR_17: cuando la consulta coincide con varias especies, el frontend
    # reenvía la misma consulta indicando cuál eligió el usuario.
    # RR_00_08: los identificadores del catálogo son slugs; cualquier otro
    # carácter se rechaza en vez de limpiarse, porque no hay forma legítima
    # de que llegue.
    especie_id: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")

    # RR_09: la conversación a la que pertenece la consulta. Sin ella se crea
    # una conversación nueva. Solo aplica a cuentas registradas.
    conversacion_id: int | None = Field(default=None, ge=1)

    # RR_17: la consulta ambigua pendiente que se está resolviendo, junto con
    # 'especie_id'. Se resuelve esa misma fila, así que no se cobra dos veces.
    consulta_id: int | None = Field(default=None, ge=1)

    @field_validator("texto")
    @classmethod
    def _texto(cls, v: str) -> str:
        # RR_00_08: se sanitiza antes de comprobar si quedó vacía, para que
        # una consulta hecha solo de marcado o caracteres invisibles se
        # rechace igual que una vacía.
        limpio = sanitizar_texto(v)
        if not limpio:
            raise ValueError("La consulta no puede estar vacía.")
        return limpio


class ConsultaOut(BaseModel):
    """Resultado de enviar una consulta (ver los estados al inicio del archivo)."""

    id: int | None = None
    # RR_09: la conversación donde quedó guardada; None para un visitante.
    conversacion_id: int | None = None
    estado: EstadoConsulta
    texto: str
    respuesta: RespuestaConsulta | None = None
    candidatos: list[EspecieCandidata] = Field(default_factory=list)
    mensaje: str | None = None
    realizada_en: datetime | None = None
    consultas_restantes: int = 0


# --- RR_09: historial por conversaciones ----------------------------------------


class ConsultaGuardada(BaseModel):
    """Una consulta dentro de una conversación, en cualquiera de sus estados.

    Una "ambigua" trae además 'candidatos' y 'mensaje', y se puede resolver
    eligiendo una especie (RR_17); una "sin_coincidencias" trae 'mensaje'.
    """

    id: int
    texto: str
    estado: EstadoConsulta
    respuesta: RespuestaConsulta | None = None
    candidatos: list[EspecieCandidata] = Field(default_factory=list)
    mensaje: str | None = None
    realizada_en: datetime


class ConversacionResumen(BaseModel):
    """Una entrada de la barra lateral."""

    model_config = {"from_attributes": True}

    id: int
    titulo: str
    creada_en: datetime
    actualizada_en: datetime


class ConversacionDetalle(ConversacionResumen):
    """Una conversación completa, con sus consultas en orden cronológico."""

    consultas: list[ConsultaGuardada] = Field(default_factory=list)
