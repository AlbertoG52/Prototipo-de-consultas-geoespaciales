"""Registro, inicio y cierre de sesión — RR_00_01, RR_00_02, RR_00_04, RR_00_05, RR_00_06, RR_00_07, RR_00_11."""
import html
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import (
    HORAS_TOKEN_VERIFICACION,
    INTENTOS_LOGIN_MAXIMOS,
    MINUTOS_BLOQUEO_LOGIN,
    MINUTOS_TOKEN_RECUPERACION,
    URL_FRONTEND,
)
from ..db import get_db
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
    ROL_USUARIO,
    TIPO_ANONIMO,
    TIPO_USUARIO,
    Identidad,
    crear_token_anonimo,
    crear_token_usuario,
    exigir_sesion,
    hash_password,
    minutos_inactividad_de,
    obtener_identidad,
    obtener_usuario_actual,
    verificar_password,
)
from ..services.correo import enviar_correo, logger
from ..services.tokens import (
    TIPO_RECUPERACION,
    TIPO_VERIFICACION,
    consumir_token,
    crear_token,
    segundos_desde_ultimo,
)
from ..services.uso import consultas_hoy, limite_de

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalizar_correo(correo: str) -> str:
    """Los correos se guardan y se buscan en minúsculas y sin espacios."""
    return correo.lower().strip()


def _usuario_por_correo(db: Session, correo: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.correo == _normalizar_correo(correo)).first()


@router.post("/registro", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
def registrar(datos: RegistroRequest, db: Session = Depends(get_db)):
    """RR_00_01 criterio 1 — crear una cuenta.

    La contraseña entra en claro y sale hasheada en la misma línea: en ningún
    momento se guarda el texto original (RR_00_02).
    """
    correo = _normalizar_correo(datos.correo)

    if _usuario_por_correo(db, correo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo.",
        )

    rol = db.query(Rol).filter(Rol.nombre == ROL_USUARIO).first()
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
        estado="activo",
        # RR_00_07 criterio 2: la cuenta nace sin verificar.
        correo_verificado=False,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    # RR_00_07 criterio 1: se envía el enlace de verificación. Si el correo no
    # sale, la cuenta igual queda creada y se puede pedir el reenvío.
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
    """Emite un token y envía por correo el enlace que lo lleva.

    Lo usan RR_00_07 (verificación) y RR_00_06 (recuperación). Devuelve False
    si el envío falló (el detalle queda en el log).
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
    """RR_00_07 criterio 1 — enlace para verificar el correo."""
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
    """RR_00_06 criterio 2 — enlace para establecer una contraseña nueva."""
    return _enviar_enlace(
        db,
        usuario,
        tipo=TIPO_RECUPERACION,
        duracion=timedelta(minutes=MINUTOS_TOKEN_RECUPERACION),
        vigencia=f"{MINUTOS_TOKEN_RECUPERACION} minutos",
        ruta="/reset-password",
        asunto="Recupera tu contraseña de FloraBot CR",
        motivo="Recibimos una solicitud para cambiar la contraseña de tu cuenta. Para elegir una nueva",
        boton="Cambiar mi contraseña",
        si_no_fuiste=(
            "Si no lo pediste, ignora este correo: tu contraseña actual sigue funcionando."
        ),
    )


def _minutos_de_bloqueo(usuario: Usuario, ahora: datetime) -> Optional[int]:
    """RR_00_05 — minutos que le quedan al bloqueo, o None si no está bloqueada."""
    if usuario.bloqueado_hasta is None or usuario.bloqueado_hasta <= ahora:
        return None
    return max(math.ceil((usuario.bloqueado_hasta - ahora).total_seconds() / 60), 1)


def _error_bloqueo(minutos: int) -> HTTPException:
    """RR_00_05 criterio 3 — avisar del bloqueo y de cuánto dura."""
    unidad = "minuto" if minutos == 1 else "minutos"
    return HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail=(
            "Tu cuenta está bloqueada temporalmente por demasiados intentos fallidos. "
            f"Intenta de nuevo en {minutos} {unidad}."
        ),
    )


@router.post("/login", response_model=TokenOut)
def iniciar_sesion(datos: LoginRequest, db: Session = Depends(get_db)):
    """RR_00_01 criterios 1 y 3 — iniciar sesión y rechazar credenciales inválidas.

    RR_00_05: tras INTENTOS_LOGIN_MAXIMOS contraseñas incorrectas seguidas la
    cuenta se bloquea MINUTOS_BLOQUEO_LOGIN minutos. Mientras dure el bloqueo
    se rechaza incluso la contraseña correcta. Un inicio de sesión correcto
    reinicia el contador.
    """
    usuario = _usuario_por_correo(db, datos.correo)
    ahora = datetime.now(timezone.utc)

    if usuario:
        minutos = _minutos_de_bloqueo(usuario, ahora)
        if minutos is not None:
            raise _error_bloqueo(minutos)

    # Un solo mensaje para correo inexistente y contraseña incorrecta: decir
    # cuál de los dos falló le confirmaría a un atacante qué correos existen.
    if not usuario or not verificar_password(datos.password, usuario.password_hash):
        if usuario:
            usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
            bloquear = usuario.intentos_fallidos >= INTENTOS_LOGIN_MAXIMOS
            if bloquear:
                usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO_LOGIN)
                usuario.intentos_fallidos = 0
            db.commit()
            if bloquear:
                raise _error_bloqueo(MINUTOS_BLOQUEO_LOGIN)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
        )

    if usuario.intentos_fallidos or usuario.bloqueado_hasta is not None:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        db.commit()

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador del sistema.",
        )

    # RR_00_07 criterios 2 y 3: sin verificar el correo la cuenta no se
    # habilita. Se comprueba después de la contraseña para no revelar nada a
    # quien no la conoce. Mientras tanto la persona puede usar el agente como
    # visitante. El frontend reconoce este caso por la frase "verificar tu correo".
    if not usuario.correo_verificado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Debes verificar tu correo antes de iniciar sesión. "
                "Revisa tu bandeja de entrada (y la carpeta de spam)."
            ),
        )

    token, _sesion_id = crear_token_usuario(usuario)
    return TokenOut(access_token=token, tipo=TIPO_USUARIO)


# Tiempo mínimo entre dos reenvíos, para no usar la cuenta de correo como spam.
SEGUNDOS_ENTRE_REENVIOS = 60


@router.post("/verificar", response_model=MensajeOut)
def verificar_correo(datos: VerificarCorreoRequest, db: Session = Depends(get_db)):
    """RR_00_07 criterio 3 — valida el enlace y habilita la cuenta."""
    fila = consumir_token(db, datos.token, TIPO_VERIFICACION)
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación no es válido, ya se usó o venció. Pide uno nuevo.",
        )

    usuario = db.get(Usuario, fila.usuario_id)
    usuario.correo_verificado = True
    db.commit()
    return MensajeOut(mensaje="¡Listo! Tu correo quedó verificado. Ya puedes iniciar sesión.")


@router.post("/reenviar-verificacion", response_model=MensajeOut)
def reenviar_verificacion(datos: CorreoRequest, db: Session = Depends(get_db)):
    """RR_00_07 — envía un enlace nuevo; el anterior deja de servir.

    Responde siempre lo mismo, exista o no la cuenta, para no revelar qué
    correos están registrados.
    """
    usuario = _usuario_por_correo(db, datos.correo)

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
    """RR_00_06 criterios 1 y 2 — envía al correo registrado un enlace de
    recuperación que vence en MINUTOS_TOKEN_RECUPERACION minutos.

    Responde siempre lo mismo, exista o no la cuenta, para no revelar qué
    correos están registrados. Una cuenta desactivada no recibe enlace.
    """
    usuario = _usuario_por_correo(db, datos.correo)

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
    """RR_00_06 criterio 3 — valida el enlace y guarda la contraseña nueva.

    Además:
    - Se quita el bloqueo por intentos fallidos (RR_00_05): quien olvidó su
      contraseña suele haber fallado varias veces.
    - El correo queda verificado (RR_00_07): abrir el enlace demuestra que la
      persona controla ese correo.
    """
    fila = consumir_token(db, datos.token, TIPO_RECUPERACION)
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace para cambiar la contraseña no es válido, ya se usó o venció. Pide uno nuevo.",
        )

    usuario = db.get(Usuario, fila.usuario_id)
    usuario.password_hash = hash_password(datos.password)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.correo_verificado = True
    db.commit()
    return MensajeOut(mensaje="Tu contraseña se cambió. Ya puedes iniciar sesión con la nueva.")


@router.post("/anonimo", response_model=TokenOut)
def sesion_anonima():
    """RR_00_11 — entrar sin cuenta.

    Emite un identificador anónimo para poder aplicarle el límite diario. No
    crea ninguna fila en 'usuarios' ni guarda nada sobre quién es.
    """
    return TokenOut(access_token=crear_token_anonimo(), tipo=TIPO_ANONIMO)


@router.get("/sesion", response_model=SesionOut)
def estado_sesion(
    identidad: Identidad = Depends(obtener_identidad),
    db: Session = Depends(get_db),
):
    """Estado de la sesión actual, sea de un usuario o de un visitante.

    El frontend lo consulta al cargar para saber qué mostrar: un visitante no
    tiene historial ni perfil, y su límite de consultas es menor.

    Si el token no sirve responde 401 (exigir_sesion), en dos casos:

    - RR_00_04: el token de un usuario venció por inactividad. El frontend
      avisa que la sesión expiró y pide un nuevo inicio de sesión, en lugar de
      convertir a la persona en visitante sin decirle nada.
    - Cualquier otro token inválido (firmado con otra SECRET_KEY o de una
      cuenta que ya no existe en esta base de datos). El frontend lo descarta y
      pide uno anónimo nuevo; si respondiera 200, el navegador se quedaría con
      un token con el que no puede enviar consultas.
    """
    exigir_sesion(identidad)

    limite = limite_de(identidad)
    usadas = consultas_hoy(db, identidad)

    return SesionOut(
        tipo=identidad.tipo,
        usuario=UsuarioOut.de_modelo(identidad.usuario) if identidad.usuario else None,
        limite_consultas=limite,
        consultas_realizadas=usadas,
        consultas_restantes=max(limite - usadas, 0),
        # RR_00_11 criterio 1: al visitante no se le guardan las consultas.
        guarda_historial=not identidad.es_anonimo,
        minutos_inactividad=(
            minutos_inactividad_de(identidad.usuario) if identidad.usuario else None
        ),
    )


@router.post("/renovar", response_model=TokenOut)
def renovar_sesion(
    identidad: Identidad = Depends(obtener_identidad),
    usuario: Usuario = Depends(obtener_usuario_actual),
):
    """RR_00_04 — extiende la sesión porque hubo actividad.

    El frontend lo llama mientras la persona usa la aplicación. Devuelve un
    token nuevo con el mismo sesion_id y otro periodo de inactividad completo.
    Un token ya vencido no llega hasta aquí (obtener_usuario_actual responde
    401): después de la inactividad no hay renovación posible, solo un nuevo
    inicio de sesión.
    """
    token, _ = crear_token_usuario(usuario, sesion_id=identidad.sesion_id or None)
    return TokenOut(access_token=token, tipo=TIPO_USUARIO)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion():
    """RR_00_01 criterio 2 — cerrar la sesión activa.

    El token es sin estado, así que el cierre efectivo lo hace el frontend al
    descartarlo. El endpoint existe para que el cierre sea una acción explícita
    del sistema y para tener dónde invalidar el token cuando se agregue una
    lista de revocación.
    """
    return None
