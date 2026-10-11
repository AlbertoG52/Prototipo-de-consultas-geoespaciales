"""Hora actual del sistema, siempre en UTC.

Todo el backend compara fechas con columnas `timestamptz`, así que usa esta
función en lugar de `datetime.now()` (que sin zona horaria devuelve la hora
local del servidor y no se puede comparar con las de la base de datos).
"""

from datetime import UTC, datetime


def ahora() -> datetime:
    """Momento actual con zona horaria UTC."""
    return datetime.now(UTC)
