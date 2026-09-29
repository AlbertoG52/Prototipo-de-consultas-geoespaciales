"""Consultas al agente e historial de la sesión — RR_02, RR_09, RR_17, RR_18."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Consulta
from ..schemas.consulta import ConsultaOut, ConsultaRequest, ItemHistorial, RespuestaConsulta
from ..security import Identidad, obtener_identidad
from ..services import catalogo
from ..services.uso import consultas_hoy, limite_de, registrar_consumo_anonimo

router = APIRouter(prefix="/consultas", tags=["consultas"])

# RR_09: cuántas consultas anteriores devuelve el historial.
LIMITE_HISTORIAL = 50


@router.post("", response_model=ConsultaOut)
def enviar_consulta(
    datos: ConsultaRequest,
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """Procesa una consulta en lenguaje natural.

    Tres caminos posibles:

    - Ninguna especie reconocida  -> estado "sin_coincidencias"
    - Varias especies reconocidas -> estado "ambigua" y la lista de candidatas
      (RR_17). El frontend muestra las opciones y reenvía la misma consulta con
      'especie_id' ya elegido.
    - Una sola especie            -> estado "resuelta" con la respuesta completa

    Solo el camino resuelto consume una consulta del límite diario: pedirle al
    usuario que desambigüe no debería costarle nada.
    """
    if identidad.es_anonimo and not identidad.anon_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida. Recarga la página para continuar.",
        )

    limite = limite_de(identidad)
    usadas = consultas_hoy(db, identidad)

    if usadas >= limite:
        detalle = (
            "Alcanzaste el límite de consultas disponibles sin cuenta. "
            "Crea una cuenta para obtener más consultas diarias."
            if identidad.es_anonimo
            else "Alcanzaste tu límite de consultas por hoy."
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detalle)

    # --- identificar la especie ---------------------------------------------
    if datos.especie_id:
        # El usuario ya eligió entre las candidatas (RR_17 criterio 3).
        elegida = catalogo.obtener_especie(datos.especie_id)
        if elegida is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La especie seleccionada no está en el catálogo.",
            )
        candidatas = [elegida]
    else:
        candidatas = catalogo.buscar_especies(datos.texto)

    if not candidatas:
        return ConsultaOut(
            estado="sin_coincidencias",
            texto=datos.texto,
            mensaje=(
                "No se reconoció ninguna especie en la consulta. "
                "Intenta con el nombre común o científico de una planta."
            ),
            consultas_restantes=max(limite - usadas, 0),
        )

    if len(candidatas) > 1:
        # RR_17 criterios 1 y 2: presentar las coincidencias para que elija.
        return ConsultaOut(
            estado="ambigua",
            texto=datos.texto,
            candidatos=candidatas,
            mensaje="La consulta coincide con más de una especie. Selecciona cuál te interesa.",
            consultas_restantes=max(limite - usadas, 0),
        )

    # --- armar la respuesta --------------------------------------------------
    respuesta = catalogo.construir_respuesta(candidatas[0].id, datos.texto)
    if respuesta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay información disponible para esa especie.",
        )

    # --- contabilizar y, si corresponde, guardar -----------------------------
    if identidad.es_anonimo:
        # RR_00_11: al visitante se le cuenta la consulta pero no se le guarda.
        registrar_consumo_anonimo(db, identidad.anon_id)
        return ConsultaOut(
            estado="resuelta",
            texto=datos.texto,
            respuesta=respuesta,
            consultas_restantes=max(limite - (usadas + 1), 0),
        )

    consulta = Consulta(
        usuario_id=identidad.usuario.id,
        texto=datos.texto,
        sesion_id=identidad.sesion_id,
        respuesta=respuesta.model_dump(mode="json"),
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)

    return ConsultaOut(
        id=consulta.id,
        estado="resuelta",
        texto=consulta.texto,
        respuesta=respuesta,
        realizada_en=consulta.realizada_en,
        consultas_restantes=max(limite - (usadas + 1), 0),
    )


@router.get("/historial", response_model=list[ItemHistorial])
def historial_de_sesion(
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """RR_09 — historial de consultas de la cuenta, la más reciente primero.

    Se filtra por usuario y no por sesión: el historial se conserva aunque la
    persona cierre sesión y vuelva a entrar con la misma cuenta. 'sesion_id'
    se sigue guardando en cada consulta, pero ya no se usa para filtrar.

    Se devuelven como máximo LIMITE_HISTORIAL consultas para que la respuesta
    no crezca sin fin con el uso.

    Un visitante anónimo recibe una lista vacía: sus consultas no se guardan
    (RR_00_11 criterio 1) y su historial vive solo en el navegador mientras no
    recargue la página.
    """
    if identidad.es_anonimo or identidad.usuario is None:
        return []

    filas = (
        db.query(Consulta)
        .filter(Consulta.usuario_id == identidad.usuario.id)
        .order_by(Consulta.realizada_en.desc(), Consulta.id.desc())
        .limit(LIMITE_HISTORIAL)
        .all()
    )

    return [
        ItemHistorial(
            id=f.id,
            texto=f.texto,
            # Guardada en la BD, así que volver a verla no reprocesa nada
            # (RR_09 criterio 2).
            respuesta=RespuestaConsulta(**f.respuesta) if f.respuesta else None,
            realizada_en=f.realizada_en,
        )
        for f in filas
    ]
