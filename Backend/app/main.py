"""Punto de entrada de la API."""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import ORIGENES_PERMITIDOS
from .db import engine
from .routers import admin, auth, consultas, conversaciones, especies, perfil
from .services import mcp_cliente

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
app.include_router(conversaciones.router)
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


@app.get("/mcp-check", tags=["estado"])
def mcp_check():
    """Verifica la conexión con CR-BioLM listando las herramientas de su servidor MCP.

    El motivo del fallo queda en el log del backend; aquí solo se informa que
    no hay conexión, para no exponer detalles internos.
    """
    try:
        herramientas = mcp_cliente.herramientas_disponibles()
    except mcp_cliente.ErrorMCP as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hay conexión con CR-BioLM. Revise que su servidor MCP esté corriendo.",
        ) from exc
    return {"conexion": "ok", "herramientas": herramientas}
