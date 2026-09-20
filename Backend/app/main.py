from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .db import engine

app = FastAPI(title="Prototipo de consultas geoespaciales - API")

# CORS abierto para desarrollo (restringir en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Chequeo simple de que la API está viva."""
    return {"status": "ok"}


@app.get("/db-check")
def db_check():
    """Verifica la conexión a la BD contando los roles cargados por las migraciones."""
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT count(*) FROM roles")).scalar()
    return {"conexion": "ok", "roles_en_bd": roles}
