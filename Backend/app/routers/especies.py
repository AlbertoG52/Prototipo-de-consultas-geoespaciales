"""Ficha completa de una especie — RR_20.

La puede ver quien pueda ver la respuesta del agente: un usuario registrado o
un visitante con sesión anónima (RR_00_11). Igual que /consultas, exige una
sesión válida, y la validación se hace en el servidor (RR_00_10). Consultar
la ficha no consume una consulta del límite diario (no pasa por el agente).
"""
from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas.consulta import FichaEspecie
from ..security import Identidad, obtener_identidad
from ..services import catalogo

router = APIRouter(prefix="/especies", tags=["especies"])


@router.get("/{especie}", response_model=FichaEspecie)
def ficha_de_especie(especie: str, identidad: Identidad = Depends(obtener_identidad)):
    """RR_20 criterio 2 — la ficha corresponde a la especie pedida.

    'especie' es el id del catálogo (o el nombre científico). Si no existe se
    responde 404 en lugar de devolver otra especie por defecto.
    """
    # Sin token válido (p. ej. una sesión vencida por inactividad, RR_00_04)
    # no hay ni usuario ni visitante: 401, y el frontend pide iniciar sesión.
    if identidad.usuario is None and not identidad.anon_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida. Recarga la página para continuar.",
        )

    ficha = catalogo.obtener_ficha(especie)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró información de esa especie.",
        )
    return ficha
