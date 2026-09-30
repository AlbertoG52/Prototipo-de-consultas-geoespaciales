"""Token temporal — mapea la tabla creada en 005 (RR_00_06 y RR_00_07)."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from ..db import Base


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    # Se guarda el hash SHA-256 del token, nunca el token que va en el enlace.
    token = Column(String(255), nullable=False, unique=True)
    tipo = Column(String(20), nullable=False)  # 'verificacion' | 'recuperacion'
    expira_en = Column(DateTime(timezone=True), nullable=False)
    usado = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
