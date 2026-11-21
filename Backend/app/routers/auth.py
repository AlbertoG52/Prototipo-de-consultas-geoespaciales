"""Registro, inicio y cierre de sesión, verificación de correo, recuperación de contraseña y
sesión anónima.
"""

import html
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import (
    HORAS_TOKEN_VERIFICACION,
    LONGITUD_MAXIMA_CONSULTA,
    MINUTOS_TOKEN_RECUPERACION,
    SEGUNDOS_MAXIMOS_CONSULTA,
    URL_FRONTEND,
)
from ..db import get_db
from ..dominio import EstadoCuenta, NombreRol, TipoSesion
from ..models import Rol, Usuario
from ..schemas.auth import (
    CorreoRequest,
    MensajeOut,
    RegistroOut,
    RestablecerPasswordRequest,
    SesionOut,
    TokenOut,
    VerificarCorreoRequest,
)
from ..schemas.usuario import LoginRequest, RegistroRequest, UsuarioOut
from ..security import (
    Identidad,
    crear_token_anonimo,
    crear_token_usuario,
    exigir_sesion,
    hash_password,
    minutos_inactividad_de,
    obtener_identidad,
    obtener_usuario_actual,
)
from ..services.autenticacion import autenticar, normalizar_correo, usuario_por_correo
from ..services.correo import enviar_correo, logger
from ..services.tokens import (
    TIPO_RECUPERACION,
    TIPO_VERIFICACION,
    consumir_token,
    crear_token,
    segundos_desde_ultimo,
)
from ..services.uso import cupo_de
from .errores import errores_http

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
def registrar(datos: RegistroRequest, db: Session = Depends(get_db)):
    """Crea una cuenta con rol usuario."""

    correo = normalizar_correo(datos.correo)

    if usuario_por_correo(db, correo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo.",
        )

    rol = db.query(Rol).filter(Rol.nombre == NombreRol.USUARIO).first()
    if rol is None:
        # Las migraciones siembran los tres roles; si falta, algo no se aplicó.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="El rol de usuario estándar no está configurado en la base de datos.",
        )

    usuario = Usuario(
        nombre=datos.nombre,
        correo=correo,
        password_hash=hash_password(datos.password),
        rol_id=rol.id,
        estado=EstadoCuenta.ACTIVO,
        # La cuenta se crea sin verificar.
        correo_verificado=False,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    # Se envía el enlace de verificación. Si el correo no sale, la cuenta queda creada y se
    # puede pedir el reenvío.
    if _enviar_verificacion(db, usuario):
        mensaje = f"Cuenta creada. Te enviamos un enlace a {correo} para verificar tu correo."
    else:
        mensaje = (
            "Cuenta creada, pero no pudimos enviar el correo de verificación. "
            "Pide que te lo reenviemos."
        )

    return RegistroOut(mensaje=mensaje, usuario=UsuarioOut.de_modelo(usuario))


def _enviar_enlace(
    db: Session,
    usuario: Usuario,
    *,
    tipo: str,
    duracion: timedelta,
    vigencia: str,
    ruta: str,
    asunto: str,
    motivo: str,
    boton: str,
    si_no_fuiste: str,
) -> bool:
    """Emite un token y envía por correo el enlace que lo lleva. Devuelve False si el envío
    falló (el detalle queda en el log).
    """
    token = crear_token(db, usuario.id, tipo, duracion)
    db.commit()

    enlace = f"{URL_FRONTEND}{ruta}?token={token}"
    nombre = usuario.nombre or "Hola"
    texto = (
        f"{nombre}:\n\n{motivo}, abre este enlace:\n\n{enlace}\n\n"
        f"El enlace vence en {vigencia} y solo se puede usar una vez.\n{si_no_fuiste}"
    )
    html_correo = (
        f"<p>{html.escape(nombre)}:</p>"
        f"<p>{html.escape(motivo)}, haz clic en el botón:</p>"
        f'<p><a href="{html.escape(enlace)}" style="display:inline-block;padding:10px 18px;'
        'background:#2d5a3d;color:#ffffff;text-decoration:none;border-radius:8px">'
        f"{html.escape(boton)}</a></p>"
        f"<p>O copia este enlace en el navegador:<br>{html.escape(enlace)}</p>"
        f"<p>El enlace vence en {vigencia} y solo se puede usar una vez. "
        f"{html.escape(si_no_fuiste)}</p>"
    )
    try:
        enviar_correo(usuario.correo, asunto, texto, html_correo)
        return True
    except Exception:
        logger.exception("No se pudo enviar el correo (%s) a %s", tipo, usuario.correo)
        return False


def _enviar_verificacion(db: Session, usuario: Usuario) -> bool:
    """Enlace para verificar el correo."""
    return _enviar_enlace(
        db,
        usuario,
        tipo=TIPO_VERIFICACION,
        duracion=timedelta(hours=HORAS_TOKEN_VERIFICACION),
        vigencia=f"{HORAS_TOKEN_VERIFICACION} horas",
        ruta="/verify-email",
        asunto="Verifica tu correo en FloraBot CR",
        motivo="Gracias por registrarte en FloraBot CR. Para activar tu cuenta",
        boton="Verificar mi correo",
        si_no_fuiste="Si no creaste esta cuenta, ignora este correo.",
    )


def _enviar_recuperacion(db: Session, usuario: Usuario) -> bool:
    """Enlace para establecer una contraseña nueva."""
    return _enviar_enlace(
        db,
        usuario,
        tipo=TIPO_RECUPERACION,
        duracion=timedelta(minutes=MINUTOS_TOKEN_RECUPERACION),
        vigencia=f"{MINUTOS_TOKEN_RECUPERACION} minutos",
        ruta="/reset-password",
        asunto="Recupera tu contraseña de FloraBot CR",
        motivo=(
            "Recibimos una solicitud para cambiar la contraseña de tu cuenta. Para elegir una nueva"
        ),
        boton="Cambiar mi contraseña",
        si_no_fuiste=(
            "Si no lo pediste, ignora este correo: tu contraseña actual sigue funcionando."
        ),
    )


@router.post("/login", response_model=TokenOut)
def iniciar_sesion(datos: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    """Inicia sesión. Las reglas (bloqueo por intentos, cuenta desactivada, correo sin
    verificar) están en services/autenticacion.py.
    """
    with errores_http():
        usuario = autenticar(db, datos.correo, datos.password)

    token, _sesion_id = crear_token_usuario(usuario)
    return TokenOut(access_token=token, tipo=TipoSesion.USUARIO)


# Tiempo mínimo entre dos reenvíos, para no usar la cuenta de correo como spam.
SEGUNDOS_ENTRE_REENVIOS = 60


@router.post("/verificar", response_model=MensajeOut)
def verificar_correo(datos: VerificarCorreoRequest, db: Session = Depends(get_db)):
    """Valida el enlace y habilita la cuenta."""
    fila = consumir_token(db, datos.token, TIPO_VERIFICACION)
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación no es válido, ya se usó o venció. Pide uno nuevo.",
        )

    usuario = db.get_one(Usuario, fila.usuario_id)
    usuario.correo_verificado = True
    db.commit()
    return MensajeOut(mensaje="¡Listo! Tu correo quedó verificado. Ya puedes iniciar sesión.")


@router.post("/reenviar-verificacion", response_model=MensajeOut)
def reenviar_verificacion(datos: CorreoRequest, db: Session = Depends(get_db)):
    """Envía un enlace de verificación nuevo; el anterior deja de servir. Responde siempre lo
    mismo, para no revelar qué correos están registrados.
    """
    usuario = usuario_por_correo(db, datos.correo)

    if usuario and usuario.activo and not usuario.correo_verificado:
        transcurridos = segundos_desde_ultimo(db, usuario.id, TIPO_VERIFICACION)
        if transcurridos is None or transcurridos >= SEGUNDOS_ENTRE_REENVIOS:
            _enviar_verificacion(db, usuario)

    return MensajeOut(
        mensaje=(
            "Si hay una cuenta pendiente de verificar con ese correo, te enviamos un enlace "
            "nuevo. Revisa tu bandeja de entrada (y la carpeta de spam)."
        )
    )


@router.post("/recuperar", response_model=MensajeOut)
def recuperar_password(datos: CorreoRequest, db: Session = Depends(get_db)):
    """Envía un enlace de recuperación que vence en MINUTOS_TOKEN_RECUPERACION minutos.
    Responde siempre lo mismo, para no revelar qué correos están registrados. Una cuenta
    desactivada no recibe enlace.
    """
    usuario = usuario_por_correo(db, datos.correo)

    if usuario and usuario.activo:
        transcurridos = segundos_desde_ultimo(db, usuario.id, TIPO_RECUPERACION)
        if transcurridos is None or transcurridos >= SEGUNDOS_ENTRE_REENVIOS:
            _enviar_recuperacion(db, usuario)

    return MensajeOut(
        mensaje=(
            "Si hay una cuenta con ese correo, te enviamos un enlace para cambiar tu contraseña. "
            f"Vence en {MINUTOS_TOKEN_RECUPERACION} minutos. Revisa tu bandeja de entrada "
            "(y la carpeta de spam)."
        )
    )


@router.post("/restablecer", response_model=MensajeOut)
def restablecer_password(datos: RestablecerPasswordRequest, db: Session = Depends(get_db)):
    """Valida el enlace y guarda la contraseña nueva. También quita el bloqueo por intentos
    fallidos y marca el correo como verificado.
    """
    fila = consumir_token(db, datos.token, TIPO_RECUPERACION)
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El enlace para cambiar la contraseña no es válido, ya se usó o venció. "
                "Pide uno nuevo."
            ),
        )

    usuario = db.get_one(Usuario, fila.usuario_id)
    usuario.password_hash = hash_password(datos.password)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.correo_verificado = True
    db.commit()
    return MensajeOut(mensaje="Tu contraseña se cambió. Ya puedes iniciar sesión con la nueva.")


@router.post("/anonimo", response_model=TokenOut)
def sesion_anonima():
    """Entrar sin cuenta: emite un identificador anónimo para aplicar el límite diario. No
    guarda nada sobre la persona.
    """
    return TokenOut(access_token=crear_token_anonimo(), tipo=TipoSesion.ANONIMO)


@router.get("/sesion", response_model=SesionOut)
def estado_sesion(
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """Estado de la sesión actual, de una cuenta o de un visitante.

    Responde 401 si el token no sirve (vencido por inactividad, firmado con otra SECRET_KEY
    o de una cuenta que ya no existe); el frontend avisa que la sesión expiró o pide un
    token anónimo nuevo.
    """
    exigir_sesion(identidad)

    # Consultas restantes del periodo y cuándo se restablecen.
    cupo = cupo_de(db, identidad)

    return SesionOut(
        tipo=identidad.tipo,
        usuario=UsuarioOut.de_modelo(identidad.usuario) if identidad.usuario else None,
        limite_consultas=cupo.limite,
        consultas_realizadas=cupo.usadas,
        consultas_restantes=cupo.restantes,
        periodo_consultas=cupo.periodo,
        consultas_se_restablecen_en=cupo.se_restablece_en,
        # Al visitante no se le guardan las consultas.
        guarda_historial=not identidad.es_anonimo,
        minutos_inactividad=(
            minutos_inactividad_de(identidad.usuario) if identidad.usuario else None
        ),
        segundos_maximos_consulta=SEGUNDOS_MAXIMOS_CONSULTA,
        longitud_maxima_consulta=LONGITUD_MAXIMA_CONSULTA,
    )


@router.post("/renovar", response_model=TokenOut)
def renovar_sesion(
    identidad: Identidad = Depends(obtener_identidad),
    usuario: Usuario = Depends(obtener_usuario_actual),
):
    """Extiende la sesión porque hubo actividad: devuelve un token nuevo con el mismo
    sesion_id. Un token ya vencido responde 401 y exige iniciar sesión de nuevo.
    """
    token, _ = crear_token_usuario(usuario, sesion_id=identidad.sesion_id or None)
    return TokenOut(access_token=token, tipo=TipoSesion.USUARIO)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion():
    """Cierra la sesión activa. El token no tiene estado, así que el cierre efectivo lo hace
    el frontend al descartarlo.
    """
    return None
