"""Esquemas de consultas y de sus respuestas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..config import LONGITUD_MAXIMA_CONSULTA
from ..sanitizacion import sanitizar_texto


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


class FichaEspecie(BaseModel):
    """RR_20 — ficha completa de una especie.

    Los campos que el catálogo no tenga llegan como None y la ficha los
    muestra como "Sin dato" en lugar de inventarlos.
    """

    id: str
    nombre_comun: str | None = None
    nombre_cientifico: str
    familia: str
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
    """Resultado de enviar una consulta.

    estado:
      - "resuelta"         -> viene 'respuesta'
      - "ambigua"          -> viene 'candidatos' (RR_17); no consume consulta
      - "sin_coincidencias"-> no se encontró la especie; no consume consulta
    """

    id: int | None = None
    estado: Literal["resuelta", "ambigua", "sin_coincidencias"]
    texto: str
    respuesta: RespuestaConsulta | None = None
    candidatos: list[EspecieCandidata] = Field(default_factory=list)
    mensaje: str | None = None
    realizada_en: datetime | None = None
    consultas_restantes: int = 0


class ItemHistorial(BaseModel):
    """Una entrada del historial de la sesión activa (RR_09)."""

    id: int
    texto: str
    respuesta: RespuestaConsulta | None = None
    realizada_en: datetime
