"""Rol del sistema — mapea la tabla creada en 001_crear_tabla_roles.sql."""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from ..db import Base


class Rol(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False, unique=True)
    descripcion = Column(String(200))

    # Cuántas consultas puede hacer al día quien tenga este rol.
    # El supermoderador lo configura (RR_63), que es de otro sprint.
    limite_consultas = Column(Integer, nullable=False, default=20)

    usuarios = relationship("Usuario", back_populates="rol")
