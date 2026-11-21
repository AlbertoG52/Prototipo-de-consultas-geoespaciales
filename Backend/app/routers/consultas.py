"""Consultas al agente. La lógica está en services/consultas.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.consulta import ConsultaOut, ConsultaRequest
from ..security import Identidad, exigir_sesion, obtener_identidad
from ..services.catalogo import FuenteCatalogo, obtener_catalogo
from ..services.consultas import procesar_consulta
from .errores import errores_http

router = APIRouter(prefix="/consultas", tags=["consultas"])


@router.post("", response_model=ConsultaOut)
def enviar_consulta(
    datos: ConsultaRequest,
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
    catalogo: FuenteCatalogo = Depends(obtener_catalogo),
) -> ConsultaOut:
    """Procesa una consulta en lenguaje natural.

    Responde "resuelta", "ambigua" (con las especies candidatas), "sin_coincidencias" u
    "orientacion". Solo "resuelta" cuenta para el límite.
    """
    exigir_sesion(identidad)
    with errores_http():
        return procesar_consulta(db, identidad, datos, catalogo)
