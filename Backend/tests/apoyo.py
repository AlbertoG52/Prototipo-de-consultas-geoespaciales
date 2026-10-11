"""Piezas comunes de las pruebas que no necesitan preparación ni limpieza.

Las que sí la necesitan (correos de prueba que se borran al terminar, buzón
falso, sesión de BD que se deshace) son fixtures en conftest.py.
"""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal
from app.dominio import TipoSesion
from app.main import app
from app.security import Identidad, hash_password

# Cliente HTTP contra la API real; las pruebas que lo usan necesitan la BD.
api = TestClient(app)

# Un visitante con sesión anónima válida (RR_00_11).
VISITANTE = Identidad(tipo=TipoSesion.ANONIMO, sesion_id="anon-1", anon_id="anon-1")

# Llegó un token, pero venció o no es válido (RR_00_04).
SESION_INVALIDA = Identidad(
    tipo=TipoSesion.ANONIMO, sesion_id="", anon_id=None, token_invalido=True
)


def sql(consulta: str, **parametros):
    """Ejecuta SQL en la BD de pruebas y confirma el cambio."""
    with SessionLocal() as db:
        resultado = db.execute(text(consulta), parametros)
        db.commit()
        return resultado


def crear_cuenta_verificada(correo: str, password: str) -> None:
    """Inserta una cuenta activa, verificada y con rol 'usuario'."""
    sql(
        "INSERT INTO usuarios (correo, password_hash, rol_id, correo_verificado) "
        "VALUES (:c, :h, (SELECT id FROM roles WHERE nombre = 'usuario'), true)",
        c=correo,
        h=hash_password(password),
    )


def usuario_falso(
    password: str | None = None, rol: str | None = "usuario", **extra
) -> SimpleNamespace:
    """Un usuario en memoria con los campos que leen los routers, sin tocar la BD.

    `password` se guarda hasheada; `rol=None` simula una cuenta sin rol.
    """
    datos = {
        "id": 7,
        "correo": "ana@test.com",
        "nombre": "Ana",
        "password_hash": hash_password(password) if password else None,
        "rol": SimpleNamespace(nombre=rol) if rol else None,
        "estado": "activo",
        "activo": True,
        "minutos_inactividad": None,
        "intentos_fallidos": 0,
        "bloqueado_hasta": None,
        "correo_verificado": True,
    }
    datos.update(extra)
    return SimpleNamespace(**datos)


class SesionFalsa:
    """Imita la sesión de BD que usan los routers.

    query(...).filter(...).first() devuelve `usuario`, y cuenta los commits
    para poder comprobar si se guardó algo.
    """

    def __init__(self, usuario=None):
        self.usuario = usuario
        self.commits = 0

    def query(self, _modelo):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return self.usuario

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        pass
