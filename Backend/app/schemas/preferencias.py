"""Esquemas de las preferencias de respuesta — RR_67, RR_68, RR_79 y RR_80."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .base import EsquemaSalida


class PreferenciasRespuesta(EsquemaSalida):
    """Si las respuestas incluyen el mapa de distribución y la lista de fuentes."""

    incluir_mapa: bool
    incluir_fuentes: bool


class PreferenciasModerador(PreferenciasRespuesta):
    """RR_67, RR_68 — las preferencias que aplican a las respuestas del moderador.

    `incluir_mapa` e `incluir_fuentes` son las que se aplican. Los campos
    `*_propio` dicen si las cambió él (True) o si sigue la del sistema (False,
    RR_80); `por_defecto` es la del sistema, para mostrarla en el perfil.
    """

    mapa_propio: bool
    fuentes_propio: bool
    por_defecto: PreferenciasRespuesta


class CambioPreferencias(BaseModel):
    """Cambio de las preferencias del moderador (PATCH /perfil/preferencias).

    Cada campo es opcional:
    - ausente: no se cambia;
    - true/false: queda como preferencia propia (RR_67, RR_68);
    - null: vuelve a usar la del sistema (RR_80).
    """

    model_config = ConfigDict(extra="forbid")

    incluir_mapa: bool | None = None
    incluir_fuentes: bool | None = None


class CambioPreferenciasPorDefecto(BaseModel):
    """RR_80 criterio 3 — el supermoderador fija el comportamiento por defecto."""

    model_config = ConfigDict(extra="forbid")

    incluir_mapa: bool
    incluir_fuentes: bool


class PreferenciasPorDefecto(PreferenciasRespuesta):
    """RR_80 — el comportamiento por defecto del sistema y su último cambio."""

    actualizado_en: datetime | None = None
    # Correo de quien hizo el último cambio; None = valor inicial.
    actualizado_por: str | None = None
