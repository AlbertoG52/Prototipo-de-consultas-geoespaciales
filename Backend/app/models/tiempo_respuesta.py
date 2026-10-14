"""Tiempo de respuesta de una consulta — tablas 015 (RR_57) y 017 (RR_33).

Lo escribe services/tiempos.py al terminar cada consulta y lo lee
GET /admin/tiempos. No guarda el texto ni quién consultó; sí la intención.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class TiempoRespuesta(Base):
    __tablename__ = "tiempos_respuesta"

    id: Mapped[int] = mapped_column(primary_key=True)
    registrada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    duracion_ms: Mapped[int]
    resultado: Mapped[str] = mapped_column(String(30))  # dominio.ResultadoConsulta
    tipo_sesion: Mapped[str] = mapped_column(String(20))  # dominio.TipoSesion
    especie_id: Mapped[str | None] = mapped_column(String(100))
    consulta_id: Mapped[int | None] = mapped_column(ForeignKey("consultas.id", ondelete="SET NULL"))
    # Tabla 017 — RR_33: qué intentó hacer el usuario (dominio.IntencionConsulta).
    intencion: Mapped[str | None] = mapped_column(String(20))
