"""Perfil del usuario: nombre, contraseña, inactividad de la sesión y preferencias de
respuesta del moderador.

Exige una cuenta; el id sale del token, nunca de la URL ni del cuerpo. Estos cambios no
pasan por la auditoría.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dominio import NombreRol, TipoSesion
from ..models import Usuario
from ..schemas.auth import TokenOut
from ..schemas.perfil import CambioInactividadRequest, CambioNombreRequest, CambioPasswordRequest
from ..schemas.preferencias import CambioPreferencias, PreferenciasModerador
from ..schemas.usuario import UsuarioOut
from ..security import (
    Identidad,
    crear_token_usuario,
    hash_password,
    obtener_identidad,
    obtener_usuario_actual,
    requiere_rol,
    verificar_password,
)
from ..services import preferencias

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.patch("", response_model=UsuarioOut)
def cambiar_nombre(
    datos: CambioNombreRequest,
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Cambia el nombre visible de la cuenta. El correo no se puede cambiar."""
    usuario.nombre = datos.nombre
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.de_modelo(usuario)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(
    datos: CambioPasswordRequest,
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Cambia la contraseña después de verificar la actual, para que una sesión abierta ajena
    no baste para quedarse con la cuenta.
    """
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta.",
        )

    if verificar_password(datos.password_nueva, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser distinta de la actual.",
        )

    # Solo se guarda el hash.
    usuario.password_hash = hash_password(datos.password_nueva)
    db.commit()


@router.patch("/inactividad", response_model=TokenOut)
def cambiar_inactividad(
    datos: CambioInactividadRequest,
    identidad: Identidad = Depends(obtener_identidad),
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Cambia el tiempo sin actividad que cierra la sesión. Devuelve un token nuevo para que
    aplique de inmediato.
    """
    usuario.minutos_inactividad = datos.minutos
    db.commit()
    db.refresh(usuario)
    token, _ = crear_token_usuario(usuario, sesion_id=identidad.sesion_id or None)
    return TokenOut(access_token=token, tipo=TipoSesion.USUARIO)


# Solo el moderador y el supermoderador configuran sus respuestas; un usuario recibe 403.
# tests/test_perfil.py exige obtener_usuario_actual en cada ruta.
_solo_moderadores = requiere_rol(NombreRol.MODERADOR, NombreRol.SUPERMODERADOR)


@router.get(
    "/preferencias",
    response_model=PreferenciasModerador,
    dependencies=[Depends(_solo_moderadores)],
)
def ver_preferencias(
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Si las respuestas del moderador incluyen el mapa y las fuentes, y si cada una es propia
    o sigue la del sistema.
    """
    return preferencias.ver_del_moderador(db, usuario)


@router.patch(
    "/preferencias",
    response_model=PreferenciasModerador,
    dependencies=[Depends(_solo_moderadores)],
)
def cambiar_preferencias(
    datos: CambioPreferencias,
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Activa o desactiva el mapa y las fuentes en las respuestas. Se guarda en la cuenta y
    aplica desde la consulta siguiente; un campo en null vuelve a la del sistema.
    """
    return preferencias.cambiar_del_moderador(db, usuario, datos)
