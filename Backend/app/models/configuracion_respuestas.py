"""Comportamiento por defecto de las respuestas (tabla configuracion_respuestas).

Tiene una sola fila (id = 1): si las respuestas incluyen el mapa y las fuentes para quien
no tiene preferencia propia. La lógica está en services/preferencias.py.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base

# Id de la única fila (la crea la migración 018).
FILA_UNICA = 1


class ConfiguracionRespuestas(Base):
    __tablename__ = "configuracion_respuestas"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=FILA_UNICA)
    incluir_mapa: Mapped[bool] = mapped_column(default=True)
    incluir_fuentes: Mapped[bool] = mapped_column(default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
