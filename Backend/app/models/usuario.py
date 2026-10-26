"""Usuario — mapea la tabla creada en 002, 006, 007, 008 y 018."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..db import Base
from ..dominio import EstadoCuenta

if TYPE_CHECKING:
    from .consulta import Consulta
    from .rol import Rol


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str | None] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(255), unique=True)

    # RR_00_02: solo el hash bcrypt.
    password_hash: Mapped[str] = mapped_column(String(255))

    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    estado: Mapped[str] = mapped_column(String(20), default=EstadoCuenta.ACTIVO)
    correo_verificado: Mapped[bool] = mapped_column(default=False)
    consultas_realizadas: Mapped[int] = mapped_column(default=0)

    # RR_00_05 / RR_00_04
    intentos_fallidos: Mapped[int] = mapped_column(default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # RR_00_04 (migración 012): NULL = valor por defecto, 0 = nunca.
    minutos_inactividad: Mapped[int | None]

    # RR_67 / RR_68 / RR_79 (migración 018): preferencia propia del moderador.
    # NULL = no la ha modificado, usa la del sistema (RR_80).
    incluir_mapa: Mapped[bool | None]
    incluir_fuentes: Mapped[bool | None]

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rol: Mapped[Rol] = relationship(back_populates="usuarios")
    consultas: Mapped[list[Consulta]] = relationship(back_populates="usuario")

    @property
    def activo(self) -> bool:
        return self.estado == EstadoCuenta.ACTIVO
