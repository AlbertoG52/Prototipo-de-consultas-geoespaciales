"""Usuario — mapea la tabla creada en 002, 006, 007 y 008."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(120))
    correo = Column(String(255), nullable=False, unique=True)

    # RR_00_02: solo el hash bcrypt.
    password_hash = Column(String(255), nullable=False)

    rol_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    estado = Column(String(20), nullable=False, default="activo")
    correo_verificado = Column(Boolean, nullable=False, default=False)
    consultas_realizadas = Column(Integer, nullable=False, default=0)

    # RR_00_05 / RR_00_04 
    intentos_fallidos = Column(Integer, nullable=False, default=0)
    bloqueado_hasta = Column(DateTime(timezone=True))
    ultimo_acceso = Column(DateTime(timezone=True))
    # RR_00_04 (migración 012): NULL = valor por defecto, 0 = nunca.
    minutos_inactividad = Column(Integer)

    # RR_67 / RR_68.
    incluir_mapa = Column(Boolean, nullable=False, default=True)
    incluir_fuentes = Column(Boolean, nullable=False, default=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now())

    rol = relationship("Rol", back_populates="usuarios")
    consultas = relationship("Consulta", back_populates="usuario")

    @property
    def activo(self) -> bool:
        return self.estado == "activo"
