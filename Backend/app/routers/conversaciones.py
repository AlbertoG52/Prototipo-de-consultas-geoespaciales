"""Historial por conversaciones — RR_09.

Cada conversación agrupa las consultas de un mismo chat, en sus tres estados
(ver migración 012). Solo existen para cuentas registradas: un visitante
recibe 401, porque sus consultas no se guardan (RR_00_11).

Cada persona solo ve sus propias conversaciones: pedir la de otra responde
404, igual que si no existiera, para no revelar qué ids existen.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dominio import EstadoConsulta
from ..models import Consulta, Conversacion, Usuario
from ..schemas.consulta import (
    ConsultaGuardada,
    ConversacionDetalle,
    ConversacionResumen,
    EspecieCandidata,
    RespuestaConsulta,
)
from ..security import obtener_usuario_actual

router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])

# Cuántas conversaciones muestra la barra lateral.
LIMITE_CONVERSACIONES = 50


@router.get("", response_model=list[ConversacionResumen])
def listar_conversaciones(
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Conversaciones de la cuenta, la de actividad más reciente primero."""
    return (
        db.query(Conversacion)
        .filter(Conversacion.usuario_id == usuario.id)
        .order_by(Conversacion.actualizada_en.desc(), Conversacion.id.desc())
        .limit(LIMITE_CONVERSACIONES)
        .all()
    )


def _a_guardada(consulta: Consulta) -> ConsultaGuardada:
    return ConsultaGuardada(
        id=consulta.id,
        texto=consulta.texto,
        estado=consulta.estado,
        respuesta=RespuestaConsulta(**consulta.respuesta) if consulta.respuesta else None,
        candidatos=[EspecieCandidata(**c) for c in (consulta.candidatos or [])]
        if consulta.estado == EstadoConsulta.AMBIGUA
        else [],
        mensaje=consulta.mensaje,
        realizada_en=consulta.realizada_en,
    )


@router.get("/{conversacion_id}", response_model=ConversacionDetalle)
def ver_conversacion(
    conversacion_id: int,
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Una conversación completa, con sus consultas en orden cronológico."""
    conversacion = (
        db.query(Conversacion)
        .filter(Conversacion.id == conversacion_id, Conversacion.usuario_id == usuario.id)
        .first()
    )
    if conversacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="La conversación no existe."
        )

    consultas = (
        db.query(Consulta)
        .filter(Consulta.conversacion_id == conversacion.id)
        .order_by(Consulta.realizada_en.asc(), Consulta.id.asc())
        .all()
    )

    return ConversacionDetalle(
        id=conversacion.id,
        titulo=conversacion.titulo,
        creada_en=conversacion.creada_en,
        actualizada_en=conversacion.actualizada_en,
        consultas=[_a_guardada(c) for c in consultas],
    )
