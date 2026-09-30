"""Ficha completa de una especie (RR_20) y sugerencias de nombres (RR_16).

Las puede usar quien pueda ver la respuesta del agente: un usuario registrado
o un visitante con sesión anónima (RR_00_11). Igual que /consultas, exigen una
sesión válida, y la validación se hace en el servidor (RR_00_10). Ninguna
consume una consulta del límite diario (no pasan por el agente).
"""
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..sanitizacion import sanitizar_texto
from ..schemas.consulta import EspecieCandidata, FichaEspecie
from ..security import Identidad, obtener_identidad
from ..services import catalogo

router = APIRouter(prefix="/especies", tags=["especies"])

LIMITE_SUGERENCIAS = 5


def _exigir_sesion(identidad: Identidad) -> None:
    # Sin token válido (p. ej. una sesión vencida por inactividad, RR_00_04)
    # no hay ni usuario ni visitante: 401, y el frontend pide iniciar sesión.
    if identidad.usuario is None and not identidad.anon_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida. Recarga la página para continuar.",
        )


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para que 'guaría' encuentre 'Guaria'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )


def coincidencias(especies: list[dict], fragmento: str) -> list[EspecieCandidata]:
    """Especies con alguna palabra del nombre común o científico que empiece por
    `fragmento`, sin repetir y en orden alfabético, hasta LIMITE_SUGERENCIAS."""
    buscado = _normalizar(fragmento)
    vistas: dict[str, EspecieCandidata] = {}
    for e in especies:
        nombres = f"{e.get('nombre_comun') or ''} {e.get('nombre_cientifico') or ''}"
        if e.get("id") not in vistas and any(
            p.startswith(buscado) for p in _normalizar(nombres).split()
        ):
            vistas[e["id"]] = EspecieCandidata(**e)
    ordenadas = sorted(vistas.values(), key=lambda c: (c.nombre_comun or c.nombre_cientifico).lower())
    return ordenadas[:LIMITE_SUGERENCIAS]


@router.get("", response_model=list[EspecieCandidata])
def sugerir_especies(
    q: str = Query(min_length=2, max_length=50),
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """RR_16 — sugerencias de especies mientras el usuario escribe.

    Los nombres salen de las respuestas ya guardadas en 'consultas': el agente
    (CR-BioLM) no ofrece una lista de especies, así que solo se sugieren las
    que alguien con cuenta ya consultó. Las de visitantes no se guardan
    (RR_00_11) y por eso no aparecen. Se leen todas las especies distintas en
    cada petición; con muchas consultas convendrá una tabla propia o un índice.
    """
    _exigir_sesion(identidad)
    fragmento = sanitizar_texto(q)
    if len(fragmento) < 2:
        return []
    especies = db.execute(
        text(
            "SELECT DISTINCT respuesta->'especie' FROM consultas "
            "WHERE estado = 'resuelta' AND respuesta->'especie' IS NOT NULL"
        )
    ).scalars()
    return coincidencias(list(especies), fragmento)


@router.get("/{especie}", response_model=FichaEspecie)
def ficha_de_especie(especie: str, identidad: Identidad = Depends(obtener_identidad)):
    """RR_20 criterio 2 — la ficha corresponde a la especie pedida.

    'especie' es el id del catálogo (o el nombre científico). Si no existe se
    responde 404 en lugar de devolver otra especie por defecto.
    """
    _exigir_sesion(identidad)
    ficha = catalogo.obtener_ficha(especie)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró información de esa especie.",
        )
    return ficha
