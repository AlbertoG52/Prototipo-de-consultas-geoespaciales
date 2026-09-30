"""Registro, inicio y cierre de sesión — RR_00_01, RR_00_02, RR_00_04, RR_00_11."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import LIMITE_CONSULTAS_ANONIMO
from ..db import get_db
from ..models import Rol, Usuario
from ..schemas.auth import RegistroOut, SesionOut, TokenOut
from ..schemas.usuario import LoginRequest, RegistroRequest, UsuarioOut
from ..security import (
    TIPO_ANONIMO,
    TIPO_USUARIO,
    Identidad,
    crear_token_anonimo,
    crear_token_usuario,
    hash_password,
    minutos_inactividad_de,
    obtener_identidad,
    obtener_usuario_actual,
    verificar_password,
)
from ..services.uso import consultas_hoy, limite_de

router = APIRouter(prefix="/auth", tags=["auth"])

ROL_POR_DEFECTO = "usuario"


def _a_salida(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id,
        nombre=usuario.nombre,
        correo=usuario.correo,
        rol=usuario.rol.nombre if usuario.rol else ROL_POR_DEFECTO,
        estado=usuario.estado,
        correo_verificado=usuario.correo_verificado,
    )


@router.post("/registro", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
def registrar(datos: RegistroRequest, db: Session = Depends(get_db)):
    """RR_00_01 criterio 1 — crear una cuenta.

    La contraseña entra en claro y sale hasheada en la misma línea: en ningún
    momento se guarda el texto original (RR_00_02).
    """
    correo = datos.correo.lower().strip()

    if db.query(Usuario).filter(Usuario.correo == correo).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo.",
        )

    rol = db.query(Rol).filter(Rol.nombre == ROL_POR_DEFECTO).first()
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
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return RegistroOut(
        mensaje="Cuenta creada. Ya puedes iniciar sesión.",
        usuario=_a_salida(usuario),
    )


@router.post("/login", response_model=TokenOut)
def iniciar_sesion(datos: LoginRequest, db: Session = Depends(get_db)):
    """RR_00_01 criterios 1 y 3 — iniciar sesión y rechazar credenciales inválidas."""
    correo = datos.correo.lower().strip()
    usuario = db.query(Usuario).filter(Usuario.correo == correo).first()

    # Un solo mensaje para correo inexistente y contraseña incorrecta: decir
    # cuál de los dos falló le confirmaría a un atacante qué correos existen.
    if not usuario or not verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador del sistema.",
        )

    token, _sesion_id = crear_token_usuario(usuario)
    return TokenOut(access_token=token, tipo=TIPO_USUARIO)


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

    RR_00_04: si llega un token vencido (por inactividad) responde 401. El
    frontend lo usa para avisar que la sesión expiró y pedir un nuevo inicio
    de sesión, en lugar de convertir a la persona en visitante sin decirle nada.
    """
    if identidad.token_invalido:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión expiró. Inicia sesión de nuevo.",
        )

    limite = limite_de(identidad)
    usadas = consultas_hoy(db, identidad)

    return SesionOut(
        tipo=identidad.tipo,
        usuario=_a_salida(identidad.usuario) if identidad.usuario else None,
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
