"""Conexión a la base de datos y sesión por petición."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Base solo para MAPEAR las tablas que ya crearon las migraciones.
# Regla del proyecto: el esquema vive en Backend/migrations/, nunca se crea
# desde el código. Por eso aquí no se llama a Base.metadata.create_all().
Base = declarative_base()


def get_db():
    """Entrega una sesión de BD por petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
