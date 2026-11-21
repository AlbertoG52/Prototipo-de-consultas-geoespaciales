"""Ficha completa de una especie, sugerencias de nombres y mapa de distribución.

Exigen una sesión válida, de cuenta o de visitante, y no cuentan para el límite de
consultas.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..dominio import EstadoConsulta
from ..sanitizacion import normalizar, sanitizar_texto
from ..schemas.consulta import EspecieCandidata, FichaEspecie
from ..security import Identidad, exigir_sesion, obtener_identidad
from ..services.catalogo import FuenteCatalogo, obtener_catalogo

router = APIRouter(prefix="/especies", tags=["especies"])

LIMITE_SUGERENCIAS = 5


def coincidencias(especies: list[dict], fragmento: str) -> list[EspecieCandidata]:
    """Especies con alguna palabra del nombre común o científico que empiece por `fragmento`,
    sin repetir, en orden alfabético del nombre científico y hasta LIMITE_SUGERENCIAS.
    """
    buscado = normalizar(fragmento)
    vistas: dict[str, EspecieCandidata] = {}
    for e in especies:
        nombres = f"{e.get('nombre_comun') or ''} {e.get('nombre_cientifico') or ''}"
        if e.get("id") not in vistas and any(
            p.startswith(buscado) for p in normalizar(nombres).split()
        ):
            vistas[e["id"]] = EspecieCandidata(**e)
    ordenadas = sorted(vistas.values(), key=lambda c: c.nombre_cientifico.lower())
    return ordenadas[:LIMITE_SUGERENCIAS]


@router.get("", response_model=list[EspecieCandidata])
def sugerir_especies(
    q: str = Query(min_length=2, max_length=50),
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """Sugerencias de especies mientras el usuario escribe.

    Salen de las respuestas ya guardadas en 'consultas', porque CR-BioLM no ofrece una
    lista de especies; por eso solo se sugieren las que ya consultó alguna cuenta.
    """
    exigir_sesion(identidad)
    fragmento = sanitizar_texto(q)
    if len(fragmento) < 2:
        return []
    especies = db.execute(
        text(
            "SELECT DISTINCT respuesta->'especie' FROM consultas "
            "WHERE estado = :estado AND respuesta->'especie' IS NOT NULL"
        ),
        {"estado": EstadoConsulta.RESUELTA},
    ).scalars()
    return coincidencias(list(especies), fragmento)


@router.get("/{especie}", response_model=FichaEspecie)
def ficha_de_especie(
    especie: str,
    identidad: Identidad = Depends(obtener_identidad),
    catalogo: FuenteCatalogo = Depends(obtener_catalogo),
) -> FichaEspecie:
    """Ficha de la especie pedida, por su id del catálogo o su nombre científico. 404 si no
    existe.
    """
    exigir_sesion(identidad)
    ficha = catalogo.obtener_ficha(especie)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró información de esa especie.",
        )
    return ficha


@router.get(
    "/{especie}/mapa",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "Mapa en PNG"}},
)
def mapa_de_especie(
    especie: str = Path(max_length=100, pattern=r"^[a-z0-9-]+$"),
    identidad: Identidad = Depends(obtener_identidad),
    catalogo: FuenteCatalogo = Depends(obtener_catalogo),
) -> Response:
    """Mapa de distribución de CR-BioLM en PNG (la `url` de RespuestaConsulta.mapa).

    Pide sesión, así que el frontend lo descarga con el token. 404 si no hay mapa.
    """
    exigir_sesion(identidad)
    png = catalogo.obtener_mapa(especie)
    if png is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay mapa de distribución para esa especie.",
        )
    return Response(
        content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"}
    )
