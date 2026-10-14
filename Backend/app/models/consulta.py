"""Consulta de un usuario registrado — tablas 004, 009 y 012.

Un visitante anónimo NO deja filas aquí: el criterio 1 de RR_00_11 dice que el
sistema no almacena sus consultas anteriores. Su conteo diario va en
ConsumoAnonimo, que guarda solo el número.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..db import Base
from ..dominio import EstadoConsulta

if TYPE_CHECKING:
    from .conversacion import Conversacion
    from .usuario import Usuario


class Consulta(Base):
    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    texto: Mapped[str] = mapped_column(Text)

    # RR_09: identifica la sesión en la que se hizo, para poder mostrar el
    # historial de la sesión activa y no todo el histórico del usuario.
    sesion_id: Mapped[str | None] = mapped_column(String(64))

    # RR_09 criterio 2: guardar la respuesta permite volver a verla sin
    # reprocesar la consulta.
    respuesta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Tabla 012 — RR_09 por conversaciones. Se guardan los tres estados; solo
    # 'resuelta' descuenta del límite diario (services/uso.py).
    conversacion_id: Mapped[int] = mapped_column(
        ForeignKey("conversaciones.id", ondelete="CASCADE")
    )
    estado: Mapped[str] = mapped_column(String(20), default=EstadoConsulta.RESUELTA)
    candidatos: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)  # solo en 'ambigua'
    mensaje: Mapped[str | None] = mapped_column(Text)  # todos menos 'resuelta'
    # Tabla 016: por qué se orientó al usuario (MotivoOrientacion); solo en 'orientacion'.
    motivo: Mapped[str | None] = mapped_column(String(20))
    # Fecha con la que se cuenta el límite.
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    realizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    usuario: Mapped[Usuario] = relationship(back_populates="consultas")
    conversacion: Mapped[Conversacion] = relationship(back_populates="consultas")
