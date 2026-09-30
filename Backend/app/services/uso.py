"""Conteo de consultas y límite diario.

RR_00_11 pide que el visitante sin cuenta tenga menos consultas
diarias que un usuario registrado. Esto centraliza ambos conteos.

Nota sobre el conteo del usuario registrado: se cuentan las filas de
'consultas' de hoy en vez de usar la columna 'usuarios.consultas_realizadas'.
Así el contador es correcto sin necesidad de un proceso que lo reinicie cada
día — el restablecimiento periódico es RR_64, de otro sprint. La columna queda
disponible para cuando ese requerimiento se implemente.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import LIMITE_CONSULTAS_ANONIMO
from ..models import Consulta, ConsumoAnonimo
from ..security import Identidad

ESTADO_RESUELTA = "resuelta"


def limite_de(identidad: Identidad) -> int:
    """Cuántas consultas diarias le corresponden a esta identidad."""
    if identidad.usuario is not None and identidad.usuario.rol is not None:
        return identidad.usuario.rol.limite_consultas
    return LIMITE_CONSULTAS_ANONIMO


def consultas_hoy(db: Session, identidad: Identidad) -> int:
    """Cuántas consultas lleva hoy esta identidad.

    Del usuario registrado se cuentan solo las consultas resueltas, por la
    fecha en que se resolvieron: las ambiguas y las sin coincidencias también
    se guardan (tabla 012) pero no cuestan, y una ambigua de ayer que se
    resuelve hoy cuenta hoy.
    """
    if identidad.usuario is not None:
        return (
            db.query(func.count(Consulta.id))
            .filter(
                Consulta.usuario_id == identidad.usuario.id,
                Consulta.estado == ESTADO_RESUELTA,
                func.date(Consulta.resuelta_en) == date.today(),
            )
            .scalar()
            or 0
        )

    if not identidad.anon_id:
        return 0

    fila = (
        db.query(ConsumoAnonimo)
        .filter(
            ConsumoAnonimo.anon_id == identidad.anon_id,
            ConsumoAnonimo.fecha == date.today(),
        )
        .first()
    )
    return fila.consultas_realizadas if fila else 0


def registrar_consumo_anonimo(db: Session, anon_id: str) -> None:
    """Suma una consulta al contador diario del visitante.

    Guarda solo el número, nunca el texto de la consulta (RR_00_11 criterio 1).
    """
    hoy = date.today()
    fila = (
        db.query(ConsumoAnonimo)
        .filter(ConsumoAnonimo.anon_id == anon_id, ConsumoAnonimo.fecha == hoy)
        .first()
    )
    if fila is None:
        fila = ConsumoAnonimo(anon_id=anon_id, fecha=hoy, consultas_realizadas=1)
        db.add(fila)
    else:
        fila.consultas_realizadas += 1
    db.commit()
