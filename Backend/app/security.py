"""Hash de contraseñas, tokens y resolución de la identidad de cada petición.

Aquí viven RR_00_02 (almacenamiento seguro de contraseñas), la mitad de
RR_00_11 (el visitante sin cuenta también recibe una identidad, anónima) y
RR_00_10 (control de acceso por rol).
"""

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

# RR_00_02 criterio 3: bcrypt es el estándar reconocido para esto.
# Nunca se guarda la contraseña en claro; solo el hash que produce este contexto.
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
    """Minutos de inactividad que cierran la sesión de este usuario — RR_00_04.

    Devuelve la preferencia del perfil si la eligió; si no, el valor por
    defecto del sistema. 0 significa que la sesión no expira por inactividad.
    """
    propio = getattr(usuario, "minutos_inactividad", None)
    return MINUTOS_INACTIVIDAD_SESION if propio is None else propio


def crear_token_usuario(usuario: Usuario, sesion_id: str | None = None) -> tuple[str, str]:
    """Token de un usuario registrado. Devuelve (token, sesion_id).

    El sesion_id se genera en cada inicio de sesión y viaja dentro del token.
    Es lo que hace posible que RR_09 muestre el historial de la sesión activa y
    no todo el histórico de la cuenta. Al renovar el token (RR_00_04) se pasa
    el sesion_id existente para que la sesión siga siendo la misma.

    RR_00_04: el token vence cuando se cumple el periodo de inactividad del
    usuario. El frontend lo renueva mientras haya actividad; si no la hay, el
    token vence en el servidor y hay que volver a autenticarse.
    """
    sesion_id = sesion_id or uuid.uuid4().hex
    minutos = minutos_inactividad_de(usuario) or MINUTOS_TOKEN_SIN_INACTIVIDAD
    token = _crear_token(
        {
            "sub": str(usuario.id),
            "tipo": TipoSesion.USUARIO,
            # Solo informativo. La autorización (RR_00_10) lee el rol desde la
            # BD en cada petición: un cambio de rol aplica de inmediato y un
            # token con este campo alterado no concede nada.
            "rol": usuario.rol.nombre if usuario.rol else None,
            "sid": sesion_id,
        },
        minutos,
    )
    return token, sesion_id


def crear_token_anonimo() -> str:
    """Token del visitante sin cuenta (RR_00_11).

    El identificador es un UUID aleatorio sin relación con ninguna persona.
    Solo sirve para llevarle el contador diario de consultas.
    """
    anon_id = uuid.uuid4().hex
    return _crear_token(
        {"sub": anon_id, "tipo": TipoSesion.ANONIMO, "sid": anon_id},
        MINUTOS_EXPIRACION_TOKEN_ANONIMO,
    )


@dataclass
class Identidad:
    """Quién está haciendo la petición: un usuario registrado o un visitante."""

    tipo: TipoSesion
    sesion_id: str
    usuario: Usuario | None = None
    anon_id: str | None = None
    # RR_00_04: llegó un token pero ya venció o no es válido. Permite avisar
    # "tu sesión expiró" en vez de tratar a la persona como visitante sin más.
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
        # Incluye el token vencido por inactividad (RR_00_04).
        return None, True


def obtener_identidad(
    request: Request,
    db: Session = Depends(get_db),
) -> Identidad:
    """Resuelve la identidad de la petición.

    Sin token válido, la petición se trata como visitante anónimo pero sin
    anon_id: puede leer, no puede consumir consultas. El frontend pide un token
    anónimo en la primera visita, así que esto es solo la red de seguridad.
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
    """Responde 401 si la petición no trae una sesión válida, de usuario o de visitante.

    Cubre el token vencido por inactividad (RR_00_04), el firmado con otra
    clave, el de una cuenta que ya no existe y la petición sin token. Ante el
    401 el frontend avisa que la sesión expiró o pide un token anónimo nuevo.
    """
    if identidad.token_invalido or (identidad.usuario is None and not identidad.anon_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión no es válida o expiró. Inicia sesión de nuevo o recarga la página.",
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


def requiere_rol(*roles_permitidos: str):
    """Dependencia que deja pasar solo a los roles indicados — RR_00_10.

    Uso: `Depends(requiere_rol(NombreRol.SUPERMODERADOR))`, en un endpoint o en
    las `dependencies` de un router completo.

    - Sin cuenta: 401 (lo lanza obtener_usuario_actual); iniciar sesión puede
      resolverlo.
    - Con cuenta pero con otro rol: 403; iniciar sesión no lo resuelve.

    Los roles se enumeran explícitamente en vez de usar una jerarquía: el
    moderador no hereda las funciones de administración del supermoderador.
    El rol sale de la BD (vía obtener_identidad), nunca del token.
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
    """bcrypt solo acepta 72 bytes; truncamos antes de hashear/verificar."""
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
