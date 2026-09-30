"""Conversación de un usuario registrado — tabla 012.

Agrupa las consultas que se hicieron en un mismo chat (RR_09). Un visitante
anónimo no tiene conversaciones guardadas (RR_00_11).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db import Base


class Conversacion(Base):
    __tablename__ = "conversaciones"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)

    # El texto de la primera consulta, recortado.
    titulo = Column(String(120), nullable=False)

    creada_en = Column(DateTime(timezone=True), server_default=func.now())
    # Se actualiza con cada consulta: la barra lateral ordena por aquí.
    actualizada_en = Column(DateTime(timezone=True), server_default=func.now())

    consultas = relationship(
        "Consulta", back_populates="conversacion", order_by="Consulta.realizada_en"
    )
