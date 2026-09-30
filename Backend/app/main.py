"""Punto de entrada de la API."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import ORIGENES_PERMITIDOS
from .db import engine
from .routers import admin, auth, consultas, especies, perfil

app = FastAPI(title="Prototipo de consultas geoespaciales - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(consultas.router)
app.include_router(admin.router)
app.include_router(perfil.router)
app.include_router(especies.router)


@app.get("/health", tags=["estado"])
def health():
    """Chequeo simple de que la API está viva."""
    return {"status": "ok"}


@app.get("/db-check", tags=["estado"])
def db_check():
    """Verifica la conexión a la BD contando los roles cargados por las migraciones."""
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT count(*) FROM roles")).scalar()
    return {"conexion": "ok", "roles_en_bd": roles}
