"""Rol del sistema — mapea la tabla creada en 001_crear_tabla_roles.sql."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .usuario import Usuario


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(200))

    # Cuántas consultas puede hacer al día quien tenga este rol.
    # El supermoderador lo configura (RR_63), que es de otro sprint.
    limite_consultas: Mapped[int] = mapped_column(default=20)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="rol")
