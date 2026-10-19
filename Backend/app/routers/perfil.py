"""Perfil del usuario autenticado: nombre, contraseña, inactividad de la sesión y
preferencias de respuesta del moderador (RR_67, RR_68, RR_79).

Todo el router exige una cuenta: un visitante anónimo recibe 401. Cada
persona solo puede modificar su propia cuenta; el id sale del token, nunca
de la URL ni del cuerpo de la petición.

Ninguno de estos cambios pasa por la auditoría (RR_00_09): el trigger de la
BD solo registra cambios de rol y de estado.
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
    """Cambia la contraseña después de verificar la actual.

    Pedir la contraseña actual evita que alguien que encuentre una sesión
    abierta pueda quedarse con la cuenta.
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

    # RR_00_02: solo se guarda el hash.
    usuario.password_hash = hash_password(datos.password_nueva)
    db.commit()


@router.patch("/inactividad", response_model=TokenOut)
def cambiar_inactividad(
    datos: CambioInactividadRequest,
    identidad: Identidad = Depends(obtener_identidad),
    usuario: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """RR_00_04 criterio 2 — cambia cuánto tiempo sin actividad cierra la sesión.

    Devuelve un token nuevo para que el periodo elegido aplique desde ya, sin
    esperar a la siguiente renovación.
    """
    usuario.minutos_inactividad = datos.minutos
    db.commit()
    db.refresh(usuario)
    token, _ = crear_token_usuario(usuario, sesion_id=identidad.sesion_id or None)
    return TokenOut(access_token=token, tipo=TipoSesion.USUARIO)


# RR_67: solo el moderador (y el supermoderador) configura sus respuestas. Un
# usuario normal recibe 403 y sus respuestas siguen la del sistema (RR_80).
# El rol va en `dependencies` y la cuenta en el parámetro, como en el resto
# del router (tests/test_perfil.py exige obtener_usuario_actual en cada ruta).
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
    """RR_67, RR_68, RR_79 — si las respuestas del moderador incluyen el mapa y las fuentes.

    Trae también si cada una es propia o sigue la del sistema (RR_80).
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
    """RR_67, RR_68 — activa o desactiva el mapa y las fuentes en las respuestas.

    Se guarda en la cuenta, así que se conserva entre sesiones y aplica desde
    la consulta siguiente (RR_79). Un campo en null vuelve a la del sistema.
    """
    return preferencias.cambiar_del_moderador(db, usuario, datos)
