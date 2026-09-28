"""Hash de contraseñas, tokens y resolución de la identidad de cada petición.

Aquí viven RR_00_02 (almacenamiento seguro de contraseñas) y la mitad de
RR_00_11 (el visitante sin cuenta también recibe una identidad, anónima).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import (
    ALGORITMO_JWT,
    MINUTOS_EXPIRACION_TOKEN,
    MINUTOS_EXPIRACION_TOKEN_ANONIMO,
    SECRET_KEY,
)
from .db import get_db
from .models import Usuario

# RR_00_02 criterio 3: bcrypt es el estándar reconocido para esto.
# Nunca se guarda la contraseña en claro; solo el hash que produce este contexto.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TIPO_USUARIO = "usuario"
TIPO_ANONIMO = "anonimo"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    return pwd_context.verify(password, hash_guardado)


def _crear_token(datos: dict, minutos: int) -> str:
    contenido = datos.copy()
    contenido["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return jwt.encode(contenido, SECRET_KEY, algorithm=ALGORITMO_JWT)


def crear_token_usuario(usuario: Usuario) -> tuple[str, str]:
    """Token de un usuario registrado. Devuelve (token, sesion_id).

    El sesion_id se genera en cada inicio de sesión y viaja dentro del token.
    Es lo que hace posible que RR_09 muestre el historial de la sesión activa y
    no todo el histórico de la cuenta.
    """
    sesion_id = uuid.uuid4().hex
    token = _crear_token(
        {
            "sub": str(usuario.id),
            "tipo": TIPO_USUARIO,
            "rol": usuario.rol.nombre if usuario.rol else None,
            "sid": sesion_id,
        },
        MINUTOS_EXPIRACION_TOKEN,
    )
    return token, sesion_id


def crear_token_anonimo() -> str:
    """Token del visitante sin cuenta (RR_00_11).

    El identificador es un UUID aleatorio sin relación con ninguna persona.
    Solo sirve para llevarle el contador diario de consultas.
    """
    anon_id = uuid.uuid4().hex
    return _crear_token({"sub": anon_id, "tipo": TIPO_ANONIMO, "sid": anon_id},
                        MINUTOS_EXPIRACION_TOKEN_ANONIMO)


@dataclass
class Identidad:
    """Quién está haciendo la petición: un usuario registrado o un visitante."""

    tipo: str
    sesion_id: str
    usuario: Optional[Usuario] = None
    anon_id: Optional[str] = None

    @property
    def es_anonimo(self) -> bool:
        return self.tipo == TIPO_ANONIMO


def _leer_token(request: Request) -> Optional[dict]:
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        return None
    token = cabecera.split(" ", 1)[1]
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITMO_JWT])
    except JWTError:
        return None


def obtener_identidad(
    request: Request,
    db: Session = Depends(get_db),
) -> Identidad:
    """Resuelve la identidad de la petición.

    Sin token válido, la petición se trata como visitante anónimo pero sin
    anon_id: puede leer, no puede consumir consultas. El frontend pide un token
    anónimo en la primera visita, así que esto es solo la red de seguridad.
    """
    datos = _leer_token(request)
    if not datos:
        return Identidad(tipo=TIPO_ANONIMO, sesion_id="", anon_id=None)

    if datos.get("tipo") == TIPO_ANONIMO:
        anon_id = datos.get("sub")
        return Identidad(tipo=TIPO_ANONIMO, sesion_id=anon_id or "", anon_id=anon_id)

    usuario = db.query(Usuario).filter(Usuario.id == int(datos["sub"])).first()
    if not usuario:
        # El token es válido pero la cuenta ya no existe.
        return Identidad(tipo=TIPO_ANONIMO, sesion_id="", anon_id=None)

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador del sistema.",
        )

    return Identidad(
        tipo=TIPO_USUARIO,
        sesion_id=datos.get("sid", ""),
        usuario=usuario,
    )


def obtener_usuario_actual(
    identidad: Identidad = Depends(obtener_identidad),
) -> Usuario:
    """Igual que obtener_identidad, pero exige una cuenta.

    Se usa en los endpoints que un visitante no debe alcanzar.
    """
    if identidad.usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Necesitas iniciar sesión para acceder a esto.",
        )
    return identidad.usuario
