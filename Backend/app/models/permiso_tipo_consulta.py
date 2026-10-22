"""Tipos de consulta permitidos por rol — mapea la tabla de 019 (RR_77).

Una fila por rol configurable y tipo de pregunta. La lógica está en
services/permisos.py.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class PermisoTipoConsulta(Base):
    __tablename__ = "permisos_tipo_consulta"

    rol: Mapped[str] = mapped_column(String(20), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), primary_key=True)
    permitido: Mapped[bool] = mapped_column(default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
