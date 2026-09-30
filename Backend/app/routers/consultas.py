"""Consultas al agente e historial — RR_02, RR_09, RR_17, RR_18."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Consulta, Conversacion
from ..schemas.consulta import (
    ConsultaOut,
    ConsultaRequest,
    EspecieCandidata,
    ItemHistorial,
    RespuestaConsulta,
)
from ..security import Identidad, obtener_identidad
from ..services import catalogo
from ..services.uso import ESTADO_RESUELTA, consultas_hoy, limite_de, registrar_consumo_anonimo

router = APIRouter(prefix="/consultas", tags=["consultas"])

# RR_09: cuántas consultas anteriores devuelve /consultas/historial.
LIMITE_HISTORIAL = 50

# Largo máximo del título de una conversación (columna de la tabla 012).
LARGO_TITULO = 120

ESTADO_AMBIGUA = "ambigua"
ESTADO_SIN_COINCIDENCIAS = "sin_coincidencias"

MENSAJE_SIN_COINCIDENCIAS = (
    "No se reconoció ninguna especie en la consulta. "
    "Intenta con el nombre común o científico de una planta."
)
MENSAJE_AMBIGUA = "La consulta coincide con más de una especie. Selecciona cuál te interesa."


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _rechazar_por_limite(identidad: Identidad, pendiente: bool = False) -> None:
    if identidad.es_anonimo:
        detalle = (
            "Alcanzaste el límite de consultas disponibles sin cuenta. "
            "Crea una cuenta para obtener más consultas diarias."
        )
    elif pendiente:
        detalle = (
            "Alcanzaste tu límite de consultas por hoy. La consulta queda pendiente: "
            "podrás elegir la especie cuando se restablezca tu límite."
        )
    else:
        detalle = "Alcanzaste tu límite de consultas por hoy."
    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detalle)


def _construir_respuesta(especie_id: str, texto: str) -> RespuestaConsulta:
    respuesta = catalogo.construir_respuesta(especie_id, texto)
    if respuesta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay información disponible para esa especie.",
        )
    return respuesta


def _conversacion_de(
    db: Session, usuario_id: int, conversacion_id: int | None, texto: str
) -> Conversacion:
    """La conversación donde se guarda la consulta; si no viene, se crea una.

    Solo se acepta una conversación del mismo usuario: con el id de otra
    persona se responde 404, igual que si no existiera.
    """
    if conversacion_id is None:
        conversacion = Conversacion(usuario_id=usuario_id, titulo=texto[:LARGO_TITULO])
        db.add(conversacion)
        db.flush()  # para tener el id antes de guardar la consulta
        return conversacion

    conversacion = (
        db.query(Conversacion)
        .filter(Conversacion.id == conversacion_id, Conversacion.usuario_id == usuario_id)
        .first()
    )
    if conversacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="La conversación no existe."
        )
    return conversacion


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
      (RR_17). El usuario elige una y el frontend reenvía la consulta con
      'especie_id' (y 'consulta_id' si es una cuenta registrada).
    - Una sola especie            -> estado "resuelta" con la respuesta completa

    Solo el camino resuelto consume una consulta del límite diario: pedirle al
    usuario que desambigüe, o avisarle que no se encontró nada, no le cuesta.

    De un usuario registrado se guardan los tres estados dentro de una
    conversación (RR_09), para poder reabrirla completa. Del visitante no se
    guarda nada (RR_00_11).
    """
    if identidad.es_anonimo and not identidad.anon_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión no es válida o venció. Intenta de nuevo.",
        )

    limite = limite_de(identidad)
    usadas = consultas_hoy(db, identidad)

    # RR_17 con cuenta: elegir la especie de una consulta ambigua ya guardada.
    if datos.consulta_id is not None:
        return _resolver_pendiente(datos, identidad, db, limite, usadas)

    if usadas >= limite:
        _rechazar_por_limite(identidad)

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
        estado, respuesta = ESTADO_SIN_COINCIDENCIAS, None
    elif len(candidatas) > 1:
        # RR_17 criterios 1 y 2: presentar las coincidencias para que elija.
        estado, respuesta = ESTADO_AMBIGUA, None
    else:
        estado = ESTADO_RESUELTA
        respuesta = _construir_respuesta(candidatas[0].id, datos.texto)

    resuelta = estado == ESTADO_RESUELTA
    mensaje = {
        ESTADO_SIN_COINCIDENCIAS: MENSAJE_SIN_COINCIDENCIAS,
        ESTADO_AMBIGUA: MENSAJE_AMBIGUA,
    }.get(estado)
    ofrecidas = candidatas if estado == ESTADO_AMBIGUA else []
    restantes = max(limite - usadas - (1 if resuelta else 0), 0)

    # --- visitante: se cuenta, pero no se guarda (RR_00_11) -----------------
    if identidad.es_anonimo:
        if resuelta:
            registrar_consumo_anonimo(db, identidad.anon_id)
        return ConsultaOut(
            estado=estado,
            texto=datos.texto,
            respuesta=respuesta,
            candidatos=ofrecidas,
            mensaje=mensaje,
            consultas_restantes=restantes,
        )

    # --- cuenta registrada: se guarda en su conversación (RR_09) ------------
    ahora = _ahora()
    conversacion = _conversacion_de(db, identidad.usuario.id, datos.conversacion_id, datos.texto)
    conversacion.actualizada_en = ahora

    consulta = Consulta(
        usuario_id=identidad.usuario.id,
        conversacion_id=conversacion.id,
        texto=datos.texto,
        sesion_id=identidad.sesion_id,
        estado=estado,
        respuesta=respuesta.model_dump(mode="json") if respuesta else None,
        candidatos=[c.model_dump(mode="json") for c in ofrecidas] or None,
        mensaje=mensaje,
        resuelta_en=ahora if resuelta else None,
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)

    return ConsultaOut(
        id=consulta.id,
        conversacion_id=conversacion.id,
        estado=estado,
        texto=consulta.texto,
        respuesta=respuesta,
        candidatos=ofrecidas,
        mensaje=mensaje,
        realizada_en=consulta.realizada_en,
        consultas_restantes=restantes,
    )


def _resolver_pendiente(
    datos: ConsultaRequest,
    identidad: Identidad,
    db: Session,
    limite: int,
    usadas: int,
) -> ConsultaOut:
    """Resuelve una consulta ambigua guardada con la especie que eligió el usuario.

    Se actualiza esa misma fila en lugar de crear otra: así la conversación
    muestra una sola consulta y se cobra una sola vez, aunque se elija la
    especie días después. La fila se bloquea mientras se resuelve, para que
    dos clics seguidos no la cobren dos veces.
    """
    if identidad.usuario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo las cuentas registradas guardan consultas pendientes.",
        )
    if not datos.especie_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Falta la especie elegida."
        )

    consulta = (
        db.query(Consulta)
        .filter(Consulta.id == datos.consulta_id, Consulta.usuario_id == identidad.usuario.id)
        .with_for_update()
        .first()
    )
    if consulta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La consulta no existe.")
    if consulta.estado != ESTADO_AMBIGUA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Esta consulta ya se resolvió."
        )

    ofrecidas = {c["id"] for c in (consulta.candidatos or [])}
    if datos.especie_id not in ofrecidas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La especie elegida no es una de las opciones de esta consulta.",
        )

    if usadas >= limite:
        _rechazar_por_limite(identidad, pendiente=True)

    respuesta = _construir_respuesta(datos.especie_id, consulta.texto)
    ahora = _ahora()

    consulta.estado = ESTADO_RESUELTA
    consulta.respuesta = respuesta.model_dump(mode="json")
    consulta.resuelta_en = ahora
    consulta.conversacion.actualizada_en = ahora
    db.commit()
    db.refresh(consulta)

    return ConsultaOut(
        id=consulta.id,
        conversacion_id=consulta.conversacion_id,
        estado=ESTADO_RESUELTA,
        texto=consulta.texto,
        respuesta=respuesta,
        realizada_en=consulta.realizada_en,
        consultas_restantes=max(limite - usadas - 1, 0),
    )


@router.get("/historial", response_model=list[ItemHistorial])
def historial_de_sesion(
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """Consultas resueltas de la cuenta, la más reciente primero.

    La barra lateral ya no usa este endpoint: muestra conversaciones
    (GET /conversaciones). Se conserva porque devuelve las respuestas en una
    lista plana, útil para vistas de uso por usuario (RR_76).

    Un visitante anónimo recibe una lista vacía: sus consultas no se guardan
    (RR_00_11 criterio 1).
    """
    if identidad.es_anonimo or identidad.usuario is None:
        return []

    filas = (
        db.query(Consulta)
        .filter(Consulta.usuario_id == identidad.usuario.id, Consulta.estado == ESTADO_RESUELTA)
        .order_by(Consulta.resuelta_en.desc(), Consulta.id.desc())
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
            realizada_en=f.resuelta_en or f.realizada_en,
        )
        for f in filas
    ]
