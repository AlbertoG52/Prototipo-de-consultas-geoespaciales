"""Conversación de un usuario registrado — tabla 012.

Agrupa las consultas que se hicieron en un mismo chat (RR_09). Un visitante
anónimo no tiene conversaciones guardadas (RR_00_11).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..db import Base

if TYPE_CHECKING:
    from .consulta import Consulta


class Conversacion(Base):
    __tablename__ = "conversaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))

    # El texto de la primera consulta, recortado.
    titulo: Mapped[str] = mapped_column(String(120))

    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Se actualiza con cada consulta: la barra lateral ordena por aquí.
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    consultas: Mapped[list[Consulta]] = relationship(
        back_populates="conversacion", order_by="Consulta.realizada_en"
    )
