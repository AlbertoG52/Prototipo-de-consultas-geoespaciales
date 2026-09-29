"""Perfil del usuario autenticado: editar su nombre y cambiar su contraseña.

Todo el router exige una cuenta: un visitante anónimo recibe 401. Cada
persona solo puede modificar su propia cuenta; el id sale del token, nunca
de la URL ni del cuerpo de la petición.

Ninguno de estos cambios pasa por la auditoría (RR_00_09): el trigger de la
BD solo registra cambios de rol y de estado.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Usuario
from ..schemas.perfil import CambioNombreRequest, CambioPasswordRequest
from ..schemas.usuario import UsuarioOut
from ..security import hash_password, obtener_usuario_actual, verificar_password

router = APIRouter(prefix="/perfil", tags=["perfil"])


def _a_salida(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id,
        nombre=usuario.nombre,
        correo=usuario.correo,
        rol=usuario.rol.nombre if usuario.rol else "usuario",
        estado=usuario.estado,
        correo_verificado=usuario.correo_verificado,
    )


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
    return _a_salida(usuario)


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
