"""Rol del sistema (tabla roles)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from ..dominio import PeriodoConsultas

if TYPE_CHECKING:
    from .usuario import Usuario


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(200))

    # Consultas permitidas en cada periodo y cada cuánto se restablece el contador. Se
    # configuran en el panel de administración.
    limite_consultas: Mapped[int] = mapped_column(default=20)
    periodo_consultas: Mapped[str] = mapped_column(String(10), default=PeriodoConsultas.DIA)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="rol")
