"""Esquemas de consultas y de sus respuestas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from ..config import LONGITUD_MAXIMA_CONSULTA
from ..dominio import DatoRespuesta, EstadoConsulta, MotivoOrientacion, TipoPregunta
from ..sanitizacion import limpiar_consulta, sanitizar_texto
from .base import EsquemaSalida

# Los estados de una consulta están en dominio.EstadoConsulta.


class RegistroPresencia(EsquemaSalida):
    """Un registro de presencia de la especie."""

    localidad: str
    fecha: str
    latitud: float
    longitud: float
    elevacion_m: int | None = None
    fuente: str


class EspecieCandidata(EsquemaSalida):
    """Una de las especies que coinciden con la consulta."""

    id: str
    nombre_comun: str | None = None
    nombre_cientifico: str
    familia: str
    # Frase de la consulta que no se encontró completa ("cedro amargo") cuando la especie
    # salió solo de una parte ("amargo"). Es interna: con ella se pide confirmar la especie
    # antes de responder.
    _frase_incompleta: str | None = PrivateAttr(default=None)

    @property
    def frase_incompleta(self) -> str | None:
        return self._frase_incompleta

    def con_frase_incompleta(self, frase: str) -> "EspecieCandidata":
        self._frase_incompleta = frase
        return self


class MapaEspecie(EsquemaSalida):
    """Mapa de distribución generado por CR-BioLM.

    El backend no dibuja mapas. Si CR-BioLM no genera uno, `mapa` es None. El PNG se pide
    aparte a `url` (GET /especies/{id}/mapa).
    """

    url: str
    capas: list[str] = Field(default_factory=list)  # qué muestra el mapa (leyenda)
    puntos: int = 0  # registros de GBIF dibujados en el mapa
    advertencia: str | None = None  # aviso de CR-BioLM sobre el mapa, si lo hay


class Procedencia(EsquemaSalida):
    """De dónde sale un dato de la respuesta.

    Ejemplo: dato="texto", fuente="Manual de Plantas de Costa Rica", detalle="Tomo V, p.
    779 · descripción".
    """

    dato: DatoRespuesta
    fuente: str
    detalle: str


class RespuestaConsulta(EsquemaSalida):
    """Lo que el agente devuelve para una consulta ya resuelta."""

    especie: EspecieCandidata
    texto: str
    elevacion: str | None = None
    registros: list[RegistroPresencia] = Field(default_factory=list)
    total_registros: int = 0
    fuentes: list[str] = Field(default_factory=list)
    mapa: MapaEspecie | None = None
    # Avisos sobre los datos de la respuesta, p. ej. que no hay registros suficientes para
    # un mapa o que GBIF no respondió.
    avisos: list[str] = Field(default_factory=list)
    # False si la consulta no pide información geográfica (pregunta cómo es la planta). Solo
    # cambia el texto.
    geoespacial: bool = True
    # Qué pregunta la consulta (distribución, hábitat, descripción o general).
    tipo: TipoPregunta = TipoPregunta.GENERAL
    procedencia: list[Procedencia] = Field(default_factory=list)
    # Cuándo descargó CR-BioLM los registros de GBIF. None si GBIF no respondió o CR-BioLM
    # no lo indica.
    registros_actualizados_en: datetime | None = None


class FichaEspecie(EspecieCandidata):
    """Ficha completa de una especie. Lo que el catálogo no tenga llega como None."""

    habitat: str | None = None
    elevacion: str | None = None
    descripcion: str | None = None
    registros: list[RegistroPresencia] = Field(default_factory=list)
    total_registros: int = 0
    fuentes: list[str] = Field(default_factory=list)
    mapa: MapaEspecie | None = None
    avisos: list[str] = Field(default_factory=list)  # igual que en RespuestaConsulta
    procedencia: list[Procedencia] = Field(default_factory=list)
    registros_actualizados_en: datetime | None = None  # igual que en RespuestaConsulta


MENSAJE_CONSULTA_VACIA = "La consulta no puede estar vacía."


def mensaje_consulta_larga(largo: int) -> str:
    """Aviso cuando la consulta supera el largo máximo."""
    return (
        f"La consulta tiene {largo} caracteres y el máximo es {LONGITUD_MAXIMA_CONSULTA}. "
        "Acórtala e intenta de nuevo."
    )


class ConsultaRequest(BaseModel):
    # El largo máximo se define en config.LONGITUD_MAXIMA_CONSULTA. Los límites de Field
    # documentan la API; el mensaje en español sale de `_largo`.
    texto: str = Field(min_length=1, max_length=LONGITUD_MAXIMA_CONSULTA)

    # Especie que eligió el usuario cuando la consulta coincide con varias. Los ids del
    # catálogo son slugs; cualquier otro carácter se rechaza.
    especie_id: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")

    # Conversación a la que pertenece la consulta; sin ella se crea una nueva. Solo para
    # cuentas registradas.
    conversacion_id: int | None = Field(default=None, ge=1)

    # Consulta ambigua pendiente que se resuelve, junto con 'especie_id'. Se actualiza esa
    # misma fila, así que no cuenta dos veces.
    consulta_id: int | None = Field(default=None, ge=1)

    @field_validator("texto", mode="before")
    @classmethod
    def _largo(cls, v: object) -> object:
        # Corre antes que los límites de Field para que el rechazo llegue en español. Se
        # mide lo que escribió el usuario, igual que el contador del frontend.
        if isinstance(v, str):
            if not v:
                raise ValueError(MENSAJE_CONSULTA_VACIA)
            if len(v) > LONGITUD_MAXIMA_CONSULTA:
                raise ValueError(mensaje_consulta_larga(len(v)))
        return v

    @field_validator("texto")
    @classmethod
    def _texto(cls, v: str) -> str:
        # Se sanitiza y limpia antes de comprobar si quedó vacía: una consulta hecha solo de
        # marcado, emojis o signos se rechaza igual que una vacía.
        limpio = limpiar_consulta(sanitizar_texto(v))
        if not limpio:
            raise ValueError(MENSAJE_CONSULTA_VACIA)
        return limpio


class ConsultaOut(EsquemaSalida):
    """Resultado de enviar una consulta."""

    id: int | None = None
    # Conversación donde quedó guardada; None para un visitante.
    conversacion_id: int | None = None
    estado: EstadoConsulta
    texto: str
    respuesta: RespuestaConsulta | None = None
    candidatos: list[EspecieCandidata] = Field(default_factory=list)
    mensaje: str | None = None
    # Solo en "orientacion": el motivo y consultas de ejemplo.
    motivo: MotivoOrientacion | None = None
    ejemplos: list[str] = Field(default_factory=list)
    realizada_en: datetime | None = None
    consultas_restantes: int = 0


# --- historial por conversaciones ------------------------------------------------


class ConsultaGuardada(EsquemaSalida):
    """Una consulta dentro de una conversación, en cualquiera de sus estados.

    "ambigua" trae 'candidatos' y 'mensaje' y se puede resolver eligiendo una especie;
    "sin_coincidencias" trae 'mensaje'; "orientacion" trae 'mensaje', 'motivo' y, según el
    motivo, 'ejemplos'.
    """

    id: int
    texto: str
    estado: EstadoConsulta
    respuesta: RespuestaConsulta | None = None
    candidatos: list[EspecieCandidata] = Field(default_factory=list)
    mensaje: str | None = None
    motivo: MotivoOrientacion | None = None
    ejemplos: list[str] = Field(default_factory=list)
    realizada_en: datetime


class ConversacionResumen(EsquemaSalida):
    """Una entrada de la barra lateral."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    creada_en: datetime
    actualizada_en: datetime


class ConversacionDetalle(ConversacionResumen):
    """Una conversación completa, con sus consultas en orden cronológico."""

    consultas: list[ConsultaGuardada] = Field(default_factory=list)
