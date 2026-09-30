"""Tokens de un solo uso para los enlaces que se envían por correo.

RR_00_07 los usa para verificar el correo y RR_00_06 para recuperar la
contraseña.

- El token que viaja en el enlace es aleatorio (secrets) e imposible de adivinar.
- En la BD se guarda solo su hash SHA-256: quien lea la tabla no obtiene
  enlaces válidos.
- Vence tras un tiempo limitado y se puede usar una sola vez.
- Al emitir uno nuevo se anulan los anteriores del mismo tipo: solo sirve el
  último enlace enviado.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Token

TIPO_VERIFICACION = "verificacion"
TIPO_RECUPERACION = "recuperacion"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def crear_token(db: Session, usuario_id: int, tipo: str, duracion: timedelta) -> str:
    """Emite un token y devuelve el valor en claro para ponerlo en el enlace.

    No hace commit: lo hace quien llama, junto con el resto de sus cambios.
    """
    db.query(Token).filter(
        Token.usuario_id == usuario_id,
        Token.tipo == tipo,
        Token.usado.is_(False),
    ).update({"usado": True}, synchronize_session=False)

    claro = secrets.token_urlsafe(32)
    db.add(
        Token(
            usuario_id=usuario_id,
            token=_hash(claro),
            tipo=tipo,
            expira_en=datetime.now(timezone.utc) + duracion,
            usado=False,
        )
    )
    return claro


def consumir_token(db: Session, claro: str, tipo: str) -> Optional[Token]:
    """Valida el token y lo marca como usado.

    Devuelve None si no existe, es de otro tipo, ya se usó o venció. No hace
    commit.
    """
    fila = db.query(Token).filter(Token.token == _hash(claro), Token.tipo == tipo).first()
    if fila is None or fila.usado or fila.expira_en <= datetime.now(timezone.utc):
        return None
    fila.usado = True
    return fila


def segundos_desde_ultimo(db: Session, usuario_id: int, tipo: str) -> Optional[float]:
    """Segundos desde que se emitió el último token de ese tipo; None si nunca."""
    ultimo = (
        db.query(Token.creado_en)
        .filter(Token.usuario_id == usuario_id, Token.tipo == tipo)
        .order_by(Token.creado_en.desc())
        .first()
    )
    if ultimo is None or ultimo[0] is None:
        return None
    return (datetime.now(timezone.utc) - ultimo[0]).total_seconds()
