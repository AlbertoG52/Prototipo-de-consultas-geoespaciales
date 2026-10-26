"""Esquemas de consultas y de sus respuestas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import LONGITUD_MAXIMA_CONSULTA
from ..dominio import DatoRespuesta, EstadoConsulta, MotivoOrientacion, TipoPregunta
from ..sanitizacion import limpiar_consulta, sanitizar_texto
from .base import EsquemaSalida

# Los estados de una consulta están en dominio.EstadoConsulta.


class RegistroPresencia(EsquemaSalida):
    """Un punto de presencia de la especie (RR_18, vista de lista)."""

    localidad: str
    fecha: str
    latitud: float
    longitud: float
    elevacion_m: int | None = None
    fuente: str


class EspecieCandidata(EsquemaSalida):
    """Una de las especies que coinciden con la consulta (RR_17)."""

    id: str
    nombre_comun: str | None = None
    nombre_cientifico: str
    familia: str


class MapaEspecie(EsquemaSalida):
    """Mapa de distribución generado por CR-BioLM (RR_41).

    El backend no dibuja mapas: todos vienen de CR-BioLM. Si CR-BioLM no
    genera uno, la respuesta trae `mapa = None` y el frontend no muestra mapa.
    La imagen PNG se pide aparte a `url` (GET /especies/{id}/mapa, con sesión).
    """

    url: str
    capas: list[str] = Field(default_factory=list)  # qué muestra el mapa (leyenda)
    puntos: int = 0  # registros de GBIF dibujados en el mapa
    advertencia: str | None = None  # aviso de CR-BioLM sobre el mapa, si lo hay


class Procedencia(EsquemaSalida):
    """RR_45 criterio 3: de dónde sale un dato de la respuesta.

    Ejemplo: dato="texto", fuente="Manual de Plantas de Costa Rica",
    detalle="Tomo V, p. 779 · descripción · fragmento más relacionado con la pregunta".
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
    # Avisos para el usuario sobre los datos de la respuesta, p. ej. que no hay
    # registros suficientes para un mapa (RR_43) o que GBIF no respondió (RR_58).
    avisos: list[str] = Field(default_factory=list)
    # RR_41: False si la consulta no pide información geográfica (pregunta cómo
    # es la planta). Solo cambia el texto: los registros y el mapa vienen igual.
    geoespacial: bool = True
    # RR_29: qué pregunta la consulta (distribución, hábitat, descripción); elige
    # el texto y se registra en tiempos_respuesta.intencion (RR_33).
    tipo: TipoPregunta = TipoPregunta.GENERAL
    procedencia: list[Procedencia] = Field(default_factory=list)  # RR_45
    # RR_56: cuándo descargó CR-BioLM los registros de GBIF (los guarda y los
    # actualiza cada cierto tiempo). None si GBIF no respondió o CR-BioLM no lo dice.
    registros_actualizados_en: datetime | None = None


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
    mapa: MapaEspecie | None = None
    avisos: list[str] = Field(default_factory=list)  # igual que en RespuestaConsulta
    procedencia: list[Procedencia] = Field(default_factory=list)  # RR_45
    registros_actualizados_en: datetime | None = None  # RR_56, igual que en RespuestaConsulta


MENSAJE_CONSULTA_VACIA = "La consulta no puede estar vacía."


def mensaje_consulta_larga(largo: int) -> str:
    """RR_34 criterio 2: el aviso cuando la consulta supera el límite."""
    return (
        f"La consulta tiene {largo} caracteres y el máximo es {LONGITUD_MAXIMA_CONSULTA}. "
        "Acórtala e intenta de nuevo."
    )


class ConsultaRequest(BaseModel):
    # RR_34: el límite se define una sola vez (config.LONGITUD_MAXIMA_CONSULTA)
    # y el frontend lo recibe en la sesión. Los límites de Field quedan para la
    # documentación de la API; los mensajes en español salen de `_largo`.
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

    @field_validator("texto", mode="before")
    @classmethod
    def _largo(cls, v: object) -> object:
        # RR_34 criterio 1: corre antes que los límites de Field para que el
        # rechazo llegue con un mensaje en español. Se mide lo que escribió el
        # usuario, igual que el contador del frontend.
        if isinstance(v, str):
            if not v:
                raise ValueError(MENSAJE_CONSULTA_VACIA)
            if len(v) > LONGITUD_MAXIMA_CONSULTA:
                raise ValueError(mensaje_consulta_larga(len(v)))
        return v

    @field_validator("texto")
    @classmethod
    def _texto(cls, v: str) -> str:
        # RR_00_08: se sanitiza antes de comprobar si quedó vacía, para que
        # una consulta hecha solo de marcado o caracteres invisibles se
        # rechace igual que una vacía. RR_21: después se limpia, así que una
        # hecha solo de emojis o signos también queda vacía.
        limpio = limpiar_consulta(sanitizar_texto(v))
        if not limpio:
            raise ValueError(MENSAJE_CONSULTA_VACIA)
        return limpio


class ConsultaOut(EsquemaSalida):
    """Resultado de enviar una consulta (ver los estados al inicio del archivo)."""

    id: int | None = None
    # RR_09: la conversación donde quedó guardada; None para un visitante.
    conversacion_id: int | None = None
    estado: EstadoConsulta
    texto: str
    respuesta: RespuestaConsulta | None = None
    candidatos: list[EspecieCandidata] = Field(default_factory=list)
    mensaje: str | None = None
    # Solo en "orientacion": por qué (saludo, ayuda...) y consultas de ejemplo
    # que el usuario puede usar (RR_40 criterio 3).
    motivo: MotivoOrientacion | None = None
    ejemplos: list[str] = Field(default_factory=list)
    realizada_en: datetime | None = None
    consultas_restantes: int = 0


# --- RR_09: historial por conversaciones ----------------------------------------


class ConsultaGuardada(EsquemaSalida):
    """Una consulta dentro de una conversación, en cualquiera de sus estados.

    Una "ambigua" trae además 'candidatos' y 'mensaje', y se puede resolver
    eligiendo una especie (RR_17); una "sin_coincidencias" trae 'mensaje'; una
    "orientacion" trae 'mensaje', 'motivo' y, según el motivo, 'ejemplos'.
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
