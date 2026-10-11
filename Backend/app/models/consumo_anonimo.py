"""Contador diario del visitante sin cuenta — tabla 010.

Guarda cuántas consultas lleva hoy un anon_id, nunca qué consultó.
Así se cumplen a la vez el criterio 1 (no se almacenan sus consultas) y el
criterio 3 (tiene un límite diario menor) de RR_00_11.
"""

from datetime import date

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ConsumoAnonimo(Base):
    __tablename__ = "consumo_anonimo"

    anon_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fecha: Mapped[date] = mapped_column(primary_key=True)
    consultas_realizadas: Mapped[int] = mapped_column(default=0)
