"""Token temporal — mapea la tabla creada en 005 (RR_00_06 y RR_00_07)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    # Se guarda el hash SHA-256 del token, nunca el token que va en el enlace.
    token: Mapped[str] = mapped_column(String(255), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))  # 'verificacion' | 'recuperacion'
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado: Mapped[bool] = mapped_column(default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
