"""Contador diario del visitante sin cuenta — tabla 010.

Guarda cuántas consultas lleva hoy un anon_id, nunca qué consultó.
Así se cumplen a la vez el criterio 1 (no se almacenan sus consultas) y el
criterio 3 (tiene un límite diario menor) de RR_00_11.
"""
from sqlalchemy import Column, Date, Integer, String

from ..db import Base


class ConsumoAnonimo(Base):
    __tablename__ = "consumo_anonimo"

    anon_id = Column(String(64), primary_key=True)
    fecha = Column(Date, primary_key=True)
    consultas_realizadas = Column(Integer, nullable=False, default=0)
