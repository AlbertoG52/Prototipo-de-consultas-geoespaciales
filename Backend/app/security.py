"""Hash de contraseñas, tokens, identidad de cada petición y control de acceso por rol."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import (
    ALGORITMO_JWT,
    MINUTOS_EXPIRACION_TOKEN_ANONIMO,
    MINUTOS_INACTIVIDAD_SESION,
    MINUTOS_TOKEN_SIN_INACTIVIDAD,
    SECRET_KEY,
)
from .db import get_db
from .dominio import TipoSesion
from .models import Usuario
from .tiempo import ahora

# bcrypt: nunca se guarda la contraseña en claro, solo su hash.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(_password_bcrypt_compatible(password))


def verificar_password(password: str, hash_guardado: str) -> bool:
    return pwd_context.verify(_password_bcrypt_compatible(password), hash_guardado)


def _crear_token(datos: dict, minutos: int) -> str:
    contenido = datos.copy()
    contenido["exp"] = ahora() + timedelta(minutes=minutos)
    return jwt.encode(contenido, SECRET_KEY, algorithm=ALGORITMO_JWT)


def minutos_inactividad_de(usuario: Usuario) -> int:
    """Minutos de inactividad que cierran la sesión del usuario: su preferencia o, si no
    eligió, la del sistema. 0 = nunca.
    """
    propio = getattr(usuario, "minutos_inactividad", None)
    return MINUTOS_INACTIVIDAD_SESION if propio is None else propio


def crear_token_usuario(usuario: Usuario, sesion_id: str | None = None) -> tuple[str, str]:
    """Token de una cuenta registrada. Devuelve (token, sesion_id).

    El sesion_id se genera en cada inicio de sesión y se conserva al renovar el token. El
    token vence al cumplirse el periodo de inactividad; el frontend lo renueva mientras
    haya actividad.
    """
    sesion_id = sesion_id or uuid.uuid4().hex
    minutos = minutos_inactividad_de(usuario) or MINUTOS_TOKEN_SIN_INACTIVIDAD
    token = _crear_token(
        {
            "sub": str(usuario.id),
            "tipo": TipoSesion.USUARIO,
            # Solo informativo: la autorización lee el rol de la BD en cada petición, así
            # que un cambio de rol aplica de inmediato.
            "rol": usuario.rol.nombre if usuario.rol else None,
            "sid": sesion_id,
        },
        minutos,
    )
    return token, sesion_id


def crear_token_anonimo() -> str:
    """Token del visitante sin cuenta. El identificador es un UUID aleatorio que solo sirve
    para contar sus consultas.
    """
    anon_id = uuid.uuid4().hex
    return _crear_token(
        {"sub": anon_id, "tipo": TipoSesion.ANONIMO, "sid": anon_id},
        MINUTOS_EXPIRACION_TOKEN_ANONIMO,
    )


@dataclass
class Identidad:
    """Quién hace la petición: una cuenta registrada o un visitante."""

    tipo: TipoSesion
    sesion_id: str
    usuario: Usuario | None = None
    anon_id: str | None = None
    # Llegó un token vencido o inválido; permite avisar que la sesión expiró.
    token_invalido: bool = False

    @property
    def es_anonimo(self) -> bool:
        return self.tipo == TipoSesion.ANONIMO


def _leer_token(request: Request) -> tuple[dict | None, bool]:
    """Devuelve (datos del token, venía un token). Sin token: (None, False)."""
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        return None, False
    token = cabecera.split(" ", 1)[1]
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITMO_JWT]), True
    except JWTError:
        # Incluye el token vencido por inactividad.
        return None, True


def obtener_identidad(
    request: Request,
    db: Session = Depends(get_db),
) -> Identidad:
    """Resuelve la identidad de la petición.

    Sin token válido se trata como visitante sin anon_id: puede leer, pero no consultar. El
    frontend pide un token anónimo en la primera visita.
    """
    datos, venia_token = _leer_token(request)
    if not datos:
        return Identidad(
            tipo=TipoSesion.ANONIMO, sesion_id="", anon_id=None, token_invalido=venia_token
        )

    if datos.get("tipo") == TipoSesion.ANONIMO:
        anon_id = datos.get("sub")
        return Identidad(tipo=TipoSesion.ANONIMO, sesion_id=anon_id or "", anon_id=anon_id)

    usuario = db.query(Usuario).filter(Usuario.id == int(datos["sub"])).first()
    if not usuario:
        # El token es válido pero la cuenta ya no existe.
        return Identidad(tipo=TipoSesion.ANONIMO, sesion_id="", anon_id=None, token_invalido=True)

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador del sistema.",
        )

    return Identidad(
        tipo=TipoSesion.USUARIO,
        sesion_id=datos.get("sid", ""),
        usuario=usuario,
    )


def exigir_sesion(identidad: Identidad) -> None:
    """Responde 401 si la petición no trae una sesión válida, de cuenta o de visitante: token
    vencido, firmado con otra clave, de una cuenta que ya no existe, o sin token.
    """
    if identidad.token_invalido or (identidad.usuario is None and not identidad.anon_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión no es válida o expiró. Inicia sesión de nuevo o recarga la página.",
        )


def obtener_usuario_actual(
    identidad: Identidad = Depends(obtener_identidad),
) -> Usuario:
    """Igual que obtener_identidad, pero exige una cuenta registrada."""
    if identidad.usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Necesitas iniciar sesión para acceder a esto.",
        )
    return identidad.usuario


def requiere_rol(*roles_permitidos: str):
    """Dependencia que deja pasar solo a los roles indicados.

    Uso: `Depends(requiere_rol(NombreRol.SUPERMODERADOR))`, en un endpoint o en las
    `dependencies` de un router. Sin cuenta responde 401; con otro rol, 403. Los roles se
    enumeran explícitamente (no hay jerarquía) y se leen de la BD, nunca del token.
    """
    if not roles_permitidos:
        raise ValueError("requiere_rol necesita al menos un rol.")
    permitidos = frozenset(roles_permitidos)

    def verificar(usuario: Usuario = Depends(obtener_usuario_actual)) -> Usuario:
        if usuario.rol is None or usuario.rol.nombre not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta acción.",
            )
        return usuario

    return verificar


def _password_bcrypt_compatible(password: str) -> str:
    """bcrypt solo acepta 72 bytes; se trunca antes de hashear y de verificar."""
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
