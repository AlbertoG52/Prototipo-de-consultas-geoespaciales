"""Consulta de un usuario registrado — tablas 004 y 009.

Un visitante anónimo NO deja filas aquí: el criterio 1 de RR_00_11 dice que el
sistema no almacena sus consultas anteriores. Su conteo diario va en
ConsumoAnonimo, que guarda solo el número.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db import Base


class Consulta(Base):
    __tablename__ = "consultas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    texto = Column(Text, nullable=False)

    # RR_09: identifica la sesión en la que se hizo, para poder mostrar el
    # historial de la sesión activa y no todo el histórico del usuario.
    sesion_id = Column(String(64))

    # RR_09 criterio 2: guardar la respuesta permite volver a verla sin
    # reprocesar la consulta.
    respuesta = Column(JSONB)

    realizada_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="consultas")
