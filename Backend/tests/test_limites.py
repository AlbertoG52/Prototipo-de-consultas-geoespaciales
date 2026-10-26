"""Pruebas de RR_62 a RR_66 — límite de consultas por rol, su periodo y el contador.

Tres grupos:

- Las de los periodos y la validación no usan la BD.
- Las del servicio (services/admin.py, services/uso.py) cambian límites de roles
  o crean consultas. Un cambio de límite deja un registro en 'auditoria', que no
  se puede borrar (RR_00_09), así que corren en la sesión `db`, que se deshace al
  final, con `commit` reemplazado por `flush`: nada queda confirmado.
- Las de la API solo leen, reciben un rechazo o agotan el límite de una cuenta de
  prueba que `correos_de_prueba` borra al terminar (con sus consultas).

Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import config
from app.db import SessionLocal
from app.dominio import EstadoConsulta, NombreRol, PeriodoConsultas, TipoSesion
from app.errores import SolicitudInvalida
from app.models import Consulta, Conversacion, Rol, Usuario
from app.schemas.admin import CambioLimite
from app.security import Identidad, crear_token_usuario
from app.services import admin, consultas
from app.services.uso import (
    consultas_del_periodo,
    consultas_por_dia,
    cupo_de,
    fin_del_periodo,
    inicio_del_periodo,
)
from app.tiempo import HORA_COSTA_RICA

from apoyo import api, crear_cuenta_verificada
from apoyo import sql as _sql

PASSWORD = "Prueba123!"
DIA, SEMANA, MES = PeriodoConsultas.DIA, PeriodoConsultas.SEMANA, PeriodoConsultas.MES

# Lunes 19/10/2026 a las 21:00 en Costa Rica, que en UTC ya es martes 20/10.
LUNES_NOCHE = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)


def _cr(*fecha: int) -> datetime:
    """Una fecha a las 00:00 (o la hora dada) de Costa Rica."""
    return datetime(*fecha, tzinfo=HORA_COSTA_RICA)


# --- RR_64: los periodos ------------------------------------------------------------


@pytest.mark.parametrize(
    ("periodo", "inicio", "fin"),
    [
        # El día es el de Costa Rica, no el de UTC (que ya es el 20).
        (DIA, _cr(2026, 10, 19), _cr(2026, 10, 20)),
        (SEMANA, _cr(2026, 10, 19), _cr(2026, 10, 26)),  # de lunes a lunes
        (MES, _cr(2026, 10, 1), _cr(2026, 11, 1)),
    ],
)
def test_inicio_y_fin_de_cada_periodo(periodo, inicio, fin):
    assert inicio_del_periodo(periodo, LUNES_NOCHE) == inicio
    assert fin_del_periodo(periodo, LUNES_NOCHE) == fin


def test_la_semana_empieza_el_lunes_aunque_sea_domingo():
    domingo = _cr(2026, 10, 25, 23, 59)
    assert inicio_del_periodo(SEMANA, domingo) == _cr(2026, 10, 19)
    assert fin_del_periodo(SEMANA, domingo) == _cr(2026, 10, 26)


@pytest.mark.parametrize(
    ("momento", "fin"),
    [
        (_cr(2026, 12, 31, 12), _cr(2027, 1, 1)),  # cambio de año
        (_cr(2027, 1, 31, 12), _cr(2027, 2, 1)),  # mes de 31 días
        (_cr(2028, 2, 29, 12), _cr(2028, 3, 1)),  # febrero bisiesto
    ],
)
def test_fin_de_mes(momento, fin):
    assert fin_del_periodo(MES, momento) == fin


def test_un_periodo_termina_donde_empieza_el_siguiente():
    for periodo in PeriodoConsultas:
        fin = fin_del_periodo(periodo, LUNES_NOCHE)
        assert inicio_del_periodo(periodo, fin) == fin


def test_consultas_por_dia_para_comparar_periodos():
    assert consultas_por_dia(20, DIA) == 20
    assert consultas_por_dia(140, SEMANA) == 20
    assert consultas_por_dia(300, MES) == 10


# --- RR_63 criterio 3: el límite debe ser un número válido -----------------------------


@pytest.mark.parametrize("valor", [20, 1, 100_000])
def test_limites_validos(valor):
    assert CambioLimite(limite_consultas=valor, periodo_consultas=DIA).limite_consultas == valor


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        (0, "entre 1 y 100 000"),
        (-5, "entre 1 y 100 000"),
        (100_001, "entre 1 y 100 000"),
        (2.5, "número entero"),
        ("20", "número entero"),
        (True, "número entero"),
        (None, "número entero"),
    ],
)
def test_limites_invalidos(valor, mensaje):
    with pytest.raises(ValidationError, match=mensaje):
        CambioLimite(limite_consultas=valor, periodo_consultas=DIA)


def test_periodo_invalido():
    with pytest.raises(ValidationError):
        CambioLimite(limite_consultas=20, periodo_consultas="año")


# --- apoyo del servicio ---------------------------------------------------------------


@pytest.fixture
def sesion(db, monkeypatch):
    """La sesión `db` sin confirmar nada: commit solo envía los cambios a la BD."""
    monkeypatch.setattr(db, "commit", db.flush)
    return db


def _crear(db: Session, correo: str, rol: NombreRol = NombreRol.USUARIO) -> Usuario:
    usuario_id = db.execute(
        text(
            "INSERT INTO usuarios (correo, password_hash, rol_id, correo_verificado) "
            "VALUES (:c, 'x', (SELECT id FROM roles WHERE nombre = :r), true) RETURNING id"
        ),
        {"c": correo, "r": rol},
    ).scalar_one()
    usuario = db.get(Usuario, usuario_id)
    assert usuario is not None
    return usuario


def _identidad(usuario: Usuario) -> Identidad:
    return Identidad(tipo=TipoSesion.USUARIO, sesion_id="s-1", usuario=usuario)


def _resuelta(db: Session, usuario: Usuario, momento: datetime) -> None:
    conversacion = Conversacion(usuario_id=usuario.id, titulo="prueba")
    db.add(conversacion)
    db.flush()
    db.add(
        Consulta(
            usuario_id=usuario.id,
            conversacion_id=conversacion.id,
            texto="prueba",
            estado=EstadoConsulta.RESUELTA,
            resuelta_en=momento,
            realizada_en=momento,
        )
    )
    db.flush()


def _limites(db: Session) -> dict[str, tuple[int, str]]:
    return {r.nombre: (r.limite_consultas, r.periodo_consultas) for r in db.query(Rol).all()}


# --- RR_63: el supermoderador define el límite de cada rol -----------------------------


def test_listar_roles_trae_limite_y_periodo(sesion):
    roles = {r.nombre: r for r in admin.listar_roles(sesion)}
    assert set(roles) == set(NombreRol)
    assert roles[NombreRol.USUARIO].limite_consultas < roles[NombreRol.MODERADOR].limite_consultas
    assert all(r.periodo_consultas in PeriodoConsultas for r in roles.values())


def test_configurar_el_limite_de_un_rol(sesion):
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)

    salida = admin.configurar_limite(sesion, actor, NombreRol.USUARIO, 60, SEMANA)

    assert (salida.limite_consultas, salida.periodo_consultas) == (60, SEMANA)
    assert _limites(sesion)[NombreRol.USUARIO] == (60, SEMANA)


def test_el_nuevo_limite_aplica_a_las_consultas_siguientes(sesion):
    """Criterio 2: la cuenta ve el nuevo límite y periodo en su siguiente petición."""
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)
    usuario = _crear(sesion, "usuario.limites@example.com")
    _resuelta(sesion, usuario, LUNES_NOCHE - timedelta(hours=1))

    admin.configurar_limite(sesion, actor, NombreRol.USUARIO, 50, SEMANA)
    sesion.expire_all()  # como en una petición nueva, que lee el rol de la BD

    cupo = cupo_de(sesion, _identidad(sesion.get(Usuario, usuario.id)), LUNES_NOCHE)
    assert (cupo.limite, cupo.periodo, cupo.usadas, cupo.restantes) == (50, SEMANA, 1, 49)
    assert cupo.se_restablece_en == _cr(2026, 10, 26)


def test_el_cambio_queda_en_la_auditoria_con_quien_lo_hizo(sesion):
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)
    antes = _limites(sesion)[NombreRol.USUARIO]

    admin.configurar_limite(sesion, actor, NombreRol.USUARIO, 60, SEMANA)

    fila = sesion.execute(
        text(
            "SELECT accion, detalle, actor_id, usuario_afectado_id FROM auditoria "
            "ORDER BY id DESC LIMIT 1"
        )
    ).one()
    periodo_antes = "día" if antes[1] == DIA else antes[1]
    assert fila.accion == "cambio_limite"
    assert fila.detalle == f"usuario: {antes[0]} por {periodo_antes} -> 60 por semana"
    assert (fila.actor_id, fila.usuario_afectado_id) == (actor.id, None)
    assert admin.listar_auditoria(sesion, 1)[0].actor == "super.limites@example.com"


# --- RR_62 criterio 3 y RR_00_11: el usuario estándar tiene menos que el moderador ------


@pytest.mark.parametrize(
    ("rol", "limite", "periodo", "mensaje"),
    [
        # Igual o más que el moderador (100 por día). El mensaje dice el máximo.
        (NombreRol.USUARIO, 100, DIA, "menor que el del moderador .*Por día, el máximo es 99"),
        (  # 1000 por semana son 142 por día
            NombreRol.USUARIO,
            1000,
            SEMANA,
            "menor que el del moderador .*Por semana, el máximo es 699",
        ),
        # El moderador por debajo del usuario (20 por día): 70 por semana son 10 por día.
        (
            NombreRol.MODERADOR,
            70,
            SEMANA,
            "menor que el del moderador .*Por semana, el moderador necesita al menos 141",
        ),
        # Menos que un visitante (5 por día). El mensaje dice el mínimo.
        (NombreRol.USUARIO, 100, MES, "más consultas que un visitante .*Por mes, el mínimo es 151"),
        (NombreRol.USUARIO, 8, SEMANA, "visitante sin cuenta .*Por semana, el mínimo es 36"),
        (NombreRol.USUARIO, 5, DIA, "más consultas que un visitante .*Por día, el mínimo es 6"),
    ],
)
def test_limites_que_no_se_aceptan(sesion, monkeypatch, rol, limite, periodo, mensaje):
    monkeypatch.setattr(config, "LIMITE_CONSULTAS_ANONIMO", 5)
    sesion.execute(
        text(
            "UPDATE roles SET limite_consultas = 20, periodo_consultas = 'dia' "
            "WHERE nombre = 'usuario'"
        )
    )
    sesion.execute(
        text(
            "UPDATE roles SET limite_consultas = 100, periodo_consultas = 'dia' "
            "WHERE nombre = 'moderador'"
        )
    )
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)
    antes = _limites(sesion)

    with pytest.raises(SolicitudInvalida, match=mensaje):
        admin.configurar_limite(sesion, actor, rol, limite, periodo)

    assert _limites(sesion) == antes  # no cambió nada


@pytest.mark.parametrize(
    ("rol", "periodo", "sugerido", "siguiente"),
    [
        (NombreRol.USUARIO, SEMANA, 36, 35),  # mínimo frente al visitante
        (NombreRol.USUARIO, MES, 151, 150),
        (NombreRol.USUARIO, DIA, 99, 100),  # máximo frente al moderador
        (NombreRol.USUARIO, SEMANA, 699, 700),
        (NombreRol.MODERADOR, SEMANA, 141, 140),  # mínimo del moderador frente al usuario
    ],
)
def test_el_valor_que_sugiere_el_mensaje_se_acepta(
    sesion, monkeypatch, rol, periodo, sugerido, siguiente
):
    """El mínimo o máximo del mensaje es exacto: se acepta, y uno más allá no."""
    monkeypatch.setattr(config, "LIMITE_CONSULTAS_ANONIMO", 5)
    sesion.execute(
        text(
            "UPDATE roles SET limite_consultas = 20, periodo_consultas = 'dia' "
            "WHERE nombre = 'usuario'"
        )
    )
    sesion.execute(
        text(
            "UPDATE roles SET limite_consultas = 100, periodo_consultas = 'dia' "
            "WHERE nombre = 'moderador'"
        )
    )
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)

    # El valor de al lado se rechaza, y el mensaje sugiere justo el que se acepta.
    with pytest.raises(SolicitudInvalida, match=rf" {sugerido}\.$"):
        admin.configurar_limite(sesion, actor, rol, siguiente, periodo)
    assert (
        admin.configurar_limite(sesion, actor, rol, sugerido, periodo).limite_consultas == sugerido
    )


def test_el_minimo_sale_del_limite_del_visitante_en_el_env(sesion, monkeypatch):
    monkeypatch.setattr(config, "LIMITE_CONSULTAS_ANONIMO", 1)
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)

    with pytest.raises(
        SolicitudInvalida, match=r"visitante sin cuenta \(1 por día\)\. Por semana, el mínimo es 8"
    ):
        admin.configurar_limite(sesion, actor, NombreRol.USUARIO, 7, SEMANA)
    assert (
        admin.configurar_limite(sesion, actor, NombreRol.USUARIO, 8, SEMANA).limite_consultas == 8
    )


def test_periodos_distintos_se_comparan_por_dia(sesion, monkeypatch):
    monkeypatch.setattr(config, "LIMITE_CONSULTAS_ANONIMO", 5)
    sesion.execute(
        text(
            "UPDATE roles SET limite_consultas = 100, periodo_consultas = 'dia' "
            "WHERE nombre = 'moderador'"
        )
    )
    actor = _crear(sesion, "super.limites@example.com", NombreRol.SUPERMODERADOR)

    # 300 por semana son unas 43 por día: más que 5 y menos que 100.
    salida = admin.configurar_limite(sesion, actor, NombreRol.USUARIO, 300, SEMANA)

    assert salida.limite_consultas == 300


# --- RR_64: el contador se restablece al empezar el periodo ------------------------------


def test_solo_cuentan_las_consultas_del_periodo_actual(sesion):
    usuario = _crear(sesion, "usuario.limites@example.com")
    identidad = _identidad(usuario)
    _resuelta(sesion, usuario, _cr(2026, 10, 18, 23, 59))  # domingo: semana anterior
    _resuelta(sesion, usuario, _cr(2026, 10, 19, 0, 0))  # lunes a las 00:00
    _resuelta(sesion, usuario, _cr(2026, 10, 19, 20, 0))

    assert consultas_del_periodo(sesion, identidad, LUNES_NOCHE) == 2  # rol 'usuario': día
    sesion.execute(text("UPDATE roles SET periodo_consultas = 'mes' WHERE nombre = 'usuario'"))
    sesion.expire_all()
    assert consultas_del_periodo(sesion, identidad, LUNES_NOCHE) == 3


def test_al_restablecerse_se_puede_volver_a_consultar(sesion):
    """Criterio 3: en el periodo siguiente vuelve a tener todo su límite."""
    usuario = _crear(sesion, "usuario.limites@example.com")
    identidad = _identidad(usuario)
    limite = usuario.rol.limite_consultas
    for _ in range(limite):
        _resuelta(sesion, usuario, LUNES_NOCHE - timedelta(minutes=5))

    ahora_mismo = cupo_de(sesion, identidad, LUNES_NOCHE)
    despues = cupo_de(sesion, identidad, ahora_mismo.se_restablece_en)

    assert ahora_mismo.restantes == 0
    assert (despues.usadas, despues.restantes) == (0, limite)


# --- RR_65: el aviso dice cuándo se restablece --------------------------------------------


def test_cuando_se_restablece():
    texto = consultas.cuando_se_restablece(_cr(2026, 10, 20))
    assert texto == "el 20/10/2026 a las 00:00 (hora de Costa Rica)"


@pytest.fixture
def cuenta(correos_de_prueba):
    """Una cuenta con rol 'usuario' y sus cabeceras."""
    correo = correos_de_prueba("limites")
    crear_cuenta_verificada(correo, PASSWORD)
    token = api.post("/auth/login", json={"correo": correo, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def _agotar(cabeceras: dict) -> None:
    """Gasta todas las consultas del periodo de la cuenta con consultas resueltas ahora."""
    restantes = api.get("/auth/sesion", headers=cabeceras).json()["consultas_restantes"]
    conversacion = api.post("/consultas", headers=cabeceras, json={"texto": "hola"}).json()
    _sql(
        "INSERT INTO consultas (usuario_id, conversacion_id, texto, estado, resuelta_en) "
        "SELECT c.usuario_id, c.id, 'relleno', 'resuelta', now() "
        "FROM conversaciones c, generate_series(1, :n) WHERE c.id = :conv",
        n=restantes,
        conv=conversacion["conversacion_id"],
    )


def test_la_sesion_dice_el_periodo_y_cuando_se_restablece(cuenta):
    """RR_66 y RR_65: el frontend muestra el contador y la fecha de reinicio."""
    sesion = api.get("/auth/sesion", headers=cuenta).json()
    with SessionLocal() as db:
        limite, periodo = (
            db.query(Rol.limite_consultas, Rol.periodo_consultas).filter_by(nombre="usuario").one()
        )
    assert sesion["limite_consultas"] == limite
    assert sesion["consultas_restantes"] == limite
    assert sesion["periodo_consultas"] == periodo
    reinicio = datetime.fromisoformat(sesion["consultas_se_restablecen_en"])
    assert reinicio == fin_del_periodo(PeriodoConsultas(periodo))


def test_con_el_limite_alcanzado_se_avisa_cuando_se_restablece(cuenta):
    """RR_65 criterios 1 a 3: antes de procesar, claro y con la fecha."""
    _agotar(cuenta)
    sesion = api.get("/auth/sesion", headers=cuenta).json()
    assert sesion["consultas_restantes"] == 0

    salida = api.post("/consultas", headers=cuenta, json={"texto": "pejibaye"})

    assert salida.status_code == 429
    reinicio = datetime.fromisoformat(sesion["consultas_se_restablecen_en"])
    fecha = reinicio.astimezone(HORA_COSTA_RICA).strftime("%d/%m/%Y")
    limite = sesion["limite_consultas"]
    assert salida.json()["detail"] == (
        f"Alcanzaste tu límite de {limite} consultas por día. "
        f"Se restablece el {fecha} a las 00:00 (hora de Costa Rica)."
    )


def test_el_visitante_tambien_sabe_cuando_se_restablece(monkeypatch):
    monkeypatch.setattr(consultas, "limite_de", lambda identidad: 0)
    token = api.post("/auth/anonimo").json()["access_token"]

    salida = api.post(
        "/consultas", headers={"Authorization": f"Bearer {token}"}, json={"texto": "pejibaye"}
    )

    assert salida.status_code == 429
    detalle = salida.json()["detail"]
    assert "por día sin cuenta. Se restablece el " in detalle
    assert detalle.endswith("Crea una cuenta para obtener más consultas.")


def test_una_consulta_resuelta_baja_el_contador(cuenta):
    """RR_66 criterio 2."""
    antes = api.get("/auth/sesion", headers=cuenta).json()["consultas_restantes"]
    assert api.post("/consultas", headers=cuenta, json={"texto": "pejibaye"}).status_code == 200
    despues = api.get("/auth/sesion", headers=cuenta).json()["consultas_restantes"]
    assert despues == antes - 1


# --- RR_63 por la API ----------------------------------------------------------------------


def _cabeceras_de(correo: str) -> dict[str, str]:
    with SessionLocal() as db:
        usuario = db.query(Usuario).filter_by(correo=correo).one()
        token, _ = crear_token_usuario(usuario)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def supermoderador(correos_de_prueba):
    correo = correos_de_prueba("super-limites")
    crear_cuenta_verificada(correo, PASSWORD, NombreRol.SUPERMODERADOR)
    return _cabeceras_de(correo)


def test_el_supermoderador_ve_los_limites(supermoderador):
    salida = api.get("/admin/roles", headers=supermoderador)
    assert salida.status_code == 200
    assert {r["nombre"] for r in salida.json()} == set(NombreRol)


@pytest.mark.parametrize("rol", [NombreRol.USUARIO, NombreRol.MODERADOR])
def test_otros_roles_no_configuran_limites(correos_de_prueba, rol):
    correo = correos_de_prueba("sin-permiso")
    crear_cuenta_verificada(correo, PASSWORD, rol)
    cabeceras = _cabeceras_de(correo)

    assert api.get("/admin/roles", headers=cabeceras).status_code == 403
    cambio = {"limite_consultas": 999, "periodo_consultas": "dia"}
    assert api.patch("/admin/roles/usuario", json=cambio, headers=cabeceras).status_code == 403


def test_la_api_rechaza_un_limite_invalido_con_el_motivo(supermoderador):
    cambio = {"limite_consultas": 0, "periodo_consultas": "dia"}
    salida = api.patch("/admin/roles/usuario", json=cambio, headers=supermoderador)
    assert salida.status_code == 422
    assert "entre 1 y 100 000" in salida.json()["detail"][0]["msg"]


def test_la_api_traduce_la_regla_entre_roles(supermoderador):
    with SessionLocal() as db:
        moderador = db.query(Rol.limite_consultas).filter_by(nombre="moderador").scalar()
        periodo = db.query(Rol.periodo_consultas).filter_by(nombre="moderador").scalar()
    cambio = {"limite_consultas": moderador, "periodo_consultas": periodo}

    salida = api.patch("/admin/roles/usuario", json=cambio, headers=supermoderador)

    assert salida.status_code == 400
    assert "debe ser menor que el del moderador" in salida.json()["detail"]


def test_un_rol_que_no_existe_responde_422(supermoderador):
    cambio = {"limite_consultas": 10, "periodo_consultas": "dia"}
    salida = api.patch("/admin/roles/invitado", json=cambio, headers=supermoderador)
    assert salida.status_code == 422
