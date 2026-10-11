"""Ficha completa de una especie (RR_20) y sugerencias de nombres (RR_16).

Las puede usar quien pueda ver la respuesta del agente: un usuario registrado
o un visitante con sesión anónima (RR_00_11). Igual que /consultas, exigen una
sesión válida, y la validación se hace en el servidor (RR_00_10). Ninguna
consume una consulta del límite diario (no pasan por el agente).
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
    """Especies con alguna palabra del nombre común o científico que empiece por
    `fragmento`, sin repetir y en orden alfabético del nombre científico (el que
    toda especie tiene; el común puede no existir), hasta LIMITE_SUGERENCIAS."""
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
    """RR_16 — sugerencias de especies mientras el usuario escribe.

    Los nombres salen de las respuestas ya guardadas en 'consultas': el agente
    (CR-BioLM) no ofrece una lista de especies, así que solo se sugieren las
    que alguien con cuenta ya consultó. Las de visitantes no se guardan
    (RR_00_11) y por eso no aparecen. Se leen todas las especies distintas en
    cada petición; con muchas consultas convendrá una tabla propia o un índice.
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
    """RR_20 criterio 2 — la ficha corresponde a la especie pedida.

    'especie' es el id del catálogo (o el nombre científico). Si no existe se
    responde 404 en lugar de devolver otra especie por defecto.
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
    """RR_41 — mapa de distribución generado por CR-BioLM, en PNG.

    Es la `url` de RespuestaConsulta.mapa. Pide sesión como el resto de
    /especies, así que el frontend lo descarga con el token (no sirve un
    <img src> directo). 404 si no hay mapa: en ese caso no se muestra ninguno.
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
