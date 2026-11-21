"""Reglas del inicio de sesión.

- Tras INTENTOS_LOGIN_MAXIMOS contraseñas incorrectas seguidas, la cuenta se bloquea
  MINUTOS_BLOQUEO_LOGIN minutos, incluso con la contraseña correcta. Un inicio correcto
  reinicia el contador.
- Una cuenta desactivada no entra.
- Una cuenta con el correo sin verificar no entra.
"""

import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..config import INTENTOS_LOGIN_MAXIMOS, MINUTOS_BLOQUEO_LOGIN
from ..errores import AccesoDenegado, CredencialesInvalidas, CuentaBloqueada
from ..models import Usuario
from ..security import verificar_password
from ..tiempo import ahora

# Un solo mensaje para correo inexistente y contraseña incorrecta, para no revelar qué
# correos existen.
MENSAJE_CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."


def normalizar_correo(correo: str) -> str:
    """Los correos se guardan y se buscan en minúsculas y sin espacios."""
    return correo.lower().strip()


def usuario_por_correo(db: Session, correo: str) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.correo == normalizar_correo(correo)).first()


def autenticar(db: Session, correo: str, password: str) -> Usuario:
    """Devuelve el usuario si puede iniciar sesión; si no, lanza el error que corresponde."""
    usuario = usuario_por_correo(db, correo)
    momento = ahora()

    if usuario:
        minutos = minutos_de_bloqueo(usuario, momento)
        if minutos is not None:
            raise _cuenta_bloqueada(minutos)

    if not usuario or not verificar_password(password, usuario.password_hash):
        if usuario:
            _registrar_intento_fallido(db, usuario, momento)
        raise CredencialesInvalidas(MENSAJE_CREDENCIALES_INVALIDAS)

    if usuario.intentos_fallidos or usuario.bloqueado_hasta is not None:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        db.commit()

    if not usuario.activo:
        raise AccesoDenegado("Tu cuenta está desactivada. Contacta al administrador del sistema.")

    # Sin verificar el correo la cuenta no se habilita. Se comprueba después de la
    # contraseña para no revelar nada a quien no la conoce. El frontend reconoce este caso
    # por la frase "verificar tu correo".
    if not usuario.correo_verificado:
        raise AccesoDenegado(
            "Debes verificar tu correo antes de iniciar sesión. "
            "Revisa tu bandeja de entrada (y la carpeta de spam)."
        )

    return usuario


def minutos_de_bloqueo(usuario: Usuario, momento: datetime) -> int | None:
    """Minutos que le quedan al bloqueo, o None si no está bloqueada."""
    if usuario.bloqueado_hasta is None or usuario.bloqueado_hasta <= momento:
        return None
    return max(math.ceil((usuario.bloqueado_hasta - momento).total_seconds() / 60), 1)


def _registrar_intento_fallido(db: Session, usuario: Usuario, momento: datetime) -> None:
    """Suma un intento fallido y, al llegar al máximo, bloquea la cuenta."""
    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
    bloquear = usuario.intentos_fallidos >= INTENTOS_LOGIN_MAXIMOS
    if bloquear:
        usuario.bloqueado_hasta = momento + timedelta(minutes=MINUTOS_BLOQUEO_LOGIN)
        usuario.intentos_fallidos = 0
    db.commit()
    if bloquear:
        raise _cuenta_bloqueada(MINUTOS_BLOQUEO_LOGIN)


def _cuenta_bloqueada(minutos: int) -> CuentaBloqueada:
    """Aviso del bloqueo y de cuánto dura."""
    unidad = "minuto" if minutos == 1 else "minutos"
    return CuentaBloqueada(
        "Tu cuenta está bloqueada temporalmente por demasiados intentos fallidos. "
        f"Intenta de nuevo en {minutos} {unidad}."
    )
