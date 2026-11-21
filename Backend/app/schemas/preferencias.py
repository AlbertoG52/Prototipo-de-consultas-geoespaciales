"""Esquemas de las preferencias de respuesta (mapa y fuentes)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .base import EsquemaSalida


class PreferenciasRespuesta(EsquemaSalida):
    """Si las respuestas incluyen el mapa de distribución y la lista de fuentes."""

    incluir_mapa: bool
    incluir_fuentes: bool


class PreferenciasModerador(PreferenciasRespuesta):
    """Preferencias que aplican a las respuestas del moderador.

    `incluir_mapa` e `incluir_fuentes` son las vigentes; `*_propio` indica si las cambió él
    o si sigue la del sistema; `por_defecto` es la del sistema.
    """

    mapa_propio: bool
    fuentes_propio: bool
    por_defecto: PreferenciasRespuesta


class CambioPreferencias(BaseModel):
    """Cambio de las preferencias del moderador (PATCH /perfil/preferencias).

    Cada campo es opcional:
    - ausente: no se cambia;
    - true/false: queda como preferencia propia;
    - null: vuelve a la del sistema.
    """

    model_config = ConfigDict(extra="forbid")

    incluir_mapa: bool | None = None
    incluir_fuentes: bool | None = None


class CambioPreferenciasPorDefecto(BaseModel):
    """El supermoderador fija el comportamiento por defecto."""

    model_config = ConfigDict(extra="forbid")

    incluir_mapa: bool
    incluir_fuentes: bool


class PreferenciasPorDefecto(PreferenciasRespuesta):
    """Comportamiento por defecto del sistema y su último cambio."""

    actualizado_en: datetime | None = None
    # Correo de quien hizo el último cambio; None = valor inicial.
    actualizado_por: str | None = None
