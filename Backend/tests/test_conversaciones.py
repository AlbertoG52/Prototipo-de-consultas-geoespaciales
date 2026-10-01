"""Pruebas de RR_09 por conversaciones y de cómo se cobra cada estado.

Usan la BD del contenedor a través de la API. Cada prueba crea sus propios
usuarios y los borra al terminar (el borrado arrastra sus conversaciones y
consultas), así que no dejan datos. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""
from datetime import datetime, timedelta, timezone

import pytest

from apoyo import api, crear_cuenta_verificada
from apoyo import sql as _sql

PASSWORD = "Clave#2024"
AMBIGUA = "guaria"                 # Guaria morada y Guaria naranja
RESUELTA = "pejibaye"
SIN_COINCIDENCIAS = "planta inventada xyz"
MORADA, NARANJA, PEJIBAYE = "guarianthe-skinneri", "guarianthe-aurantiaca", "bactris-gasipaes"


@pytest.fixture
def crear_cuenta(correos_de_prueba):
    """Devuelve una función que crea una cuenta y entrega sus cabeceras."""

    def crear() -> dict:
        correo = correos_de_prueba()
        crear_cuenta_verificada(correo, PASSWORD)
        token = api.post("/auth/login", json={"correo": correo, "password": PASSWORD}).json()
        return {"Authorization": f"Bearer {token['access_token']}"}

    return crear


def _consultar(cabeceras, texto, **extra):
    return api.post("/consultas", headers=cabeceras, json={"texto": texto, **extra})


def _restantes(cabeceras) -> int:
    return api.get("/auth/sesion", headers=cabeceras).json()["consultas_restantes"]


# --- se guardan los tres estados, pero solo cobra la resuelta ---------------

def test_los_tres_estados_se_guardan_en_la_misma_conversacion(crear_cuenta):
    yo = crear_cuenta()
    inicio = _restantes(yo)

    sin = _consultar(yo, SIN_COINCIDENCIAS).json()
    conversacion = sin["conversacion_id"]
    ambigua = _consultar(yo, AMBIGUA, conversacion_id=conversacion).json()
    resuelta = _consultar(yo, RESUELTA, conversacion_id=conversacion).json()

    assert [sin["estado"], ambigua["estado"], resuelta["estado"]] == [
        "sin_coincidencias", "ambigua", "resuelta"]
    assert ambigua["conversacion_id"] == resuelta["conversacion_id"] == conversacion
    assert _restantes(yo) == inicio - 1  # solo la resuelta descontó

    detalle = api.get(f"/conversaciones/{conversacion}", headers=yo).json()
    assert detalle["titulo"] == SIN_COINCIDENCIAS  # el título es la primera consulta
    assert [c["estado"] for c in detalle["consultas"]] == ["sin_coincidencias", "ambigua", "resuelta"]
    pendiente = detalle["consultas"][1]
    assert {c["id"] for c in pendiente["candidatos"]} == {MORADA, NARANJA}
    assert detalle["consultas"][2]["respuesta"]["especie"]["id"] == PEJIBAYE


def test_sin_conversacion_se_crea_una_nueva(crear_cuenta):
    yo = crear_cuenta()
    a = _consultar(yo, RESUELTA).json()["conversacion_id"]
    b = _consultar(yo, RESUELTA).json()["conversacion_id"]
    assert a != b
    lista = api.get("/conversaciones", headers=yo).json()
    assert [c["id"] for c in lista] == [b, a]  # la más reciente primero


# --- RR_17: la ambigua queda pendiente y se retoma sin cobrar doble ---------

def test_resolver_una_ambigua_pendiente_cobra_una_sola_vez(crear_cuenta):
    yo = crear_cuenta()
    inicio = _restantes(yo)
    pendiente = _consultar(yo, AMBIGUA).json()

    elegida = _consultar(yo, AMBIGUA, consulta_id=pendiente["id"], especie_id=NARANJA)
    assert elegida.status_code == 200
    assert elegida.json()["estado"] == "resuelta"
    assert elegida.json()["id"] == pendiente["id"]  # es la misma fila, no otra
    assert elegida.json()["respuesta"]["especie"]["id"] == NARANJA
    assert _restantes(yo) == inicio - 1

    otra_vez = _consultar(yo, AMBIGUA, consulta_id=pendiente["id"], especie_id=MORADA)
    assert otra_vez.status_code == 409
    assert _restantes(yo) == inicio - 1  # el segundo clic no cobró

    detalle = api.get(f"/conversaciones/{pendiente['conversacion_id']}", headers=yo).json()
    assert len(detalle["consultas"]) == 1
    assert detalle["consultas"][0]["estado"] == "resuelta"
    assert detalle["consultas"][0]["candidatos"] == []


def test_solo_se_puede_elegir_una_de_las_opciones(crear_cuenta):
    yo = crear_cuenta()
    pendiente = _consultar(yo, AMBIGUA).json()
    r = _consultar(yo, AMBIGUA, consulta_id=pendiente["id"], especie_id=PEJIBAYE)
    assert r.status_code == 400


def test_sin_consultas_disponibles_la_ambigua_sigue_pendiente(crear_cuenta):
    yo = crear_cuenta()
    pendiente = _consultar(yo, AMBIGUA).json()
    # Se agota el límite con consultas resueltas hoy.
    _sql(
        "INSERT INTO consultas (usuario_id, conversacion_id, texto, estado, resuelta_en) "
        "SELECT c.usuario_id, c.id, 'relleno', 'resuelta', now() "
        "FROM conversaciones c, generate_series(1, :n) WHERE c.id = :conv",
        n=_restantes(yo),
        conv=pendiente["conversacion_id"],
    )
    assert _restantes(yo) == 0

    r = _consultar(yo, AMBIGUA, consulta_id=pendiente["id"], especie_id=MORADA)
    assert r.status_code == 429
    detalle = api.get(f"/conversaciones/{pendiente['conversacion_id']}", headers=yo).json()
    assert detalle["consultas"][0]["estado"] == "ambigua"


def test_el_limite_cuenta_por_la_fecha_en_que_se_resolvio(crear_cuenta):
    yo = crear_cuenta()
    inicio = _restantes(yo)
    conversacion = _consultar(yo, SIN_COINCIDENCIAS).json()["conversacion_id"]
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    # Resuelta ayer: no cuenta hoy. Pendiente de ayer: tampoco.
    _sql(
        "INSERT INTO consultas (usuario_id, conversacion_id, texto, estado, realizada_en, resuelta_en) "
        "SELECT usuario_id, id, 'ayer', 'resuelta', :ayer, :ayer FROM conversaciones WHERE id = :conv",
        ayer=ayer, conv=conversacion,
    )
    pendiente_de_ayer = _sql(
        "INSERT INTO consultas (usuario_id, conversacion_id, texto, estado, candidatos, realizada_en) "
        "SELECT usuario_id, id, :t, 'ambigua', CAST(:cand AS jsonb), :ayer "
        "FROM conversaciones WHERE id = :conv RETURNING id",
        t=AMBIGUA, ayer=ayer, conv=conversacion,
        cand=f'[{{"id": "{MORADA}", "nombre_cientifico": "x", "familia": "y"}}]',
    ).scalar()
    assert _restantes(yo) == inicio

    # Al resolverla hoy, cuenta hoy.
    r = _consultar(yo, AMBIGUA, consulta_id=pendiente_de_ayer, especie_id=MORADA)
    assert r.status_code == 200
    assert _restantes(yo) == inicio - 1


# --- acceso ------------------------------------------------------------------

def test_nadie_ve_ni_escribe_en_conversaciones_ajenas(crear_cuenta):
    yo, otra = crear_cuenta(), crear_cuenta()
    mia = _consultar(yo, AMBIGUA).json()

    assert api.get(f"/conversaciones/{mia['conversacion_id']}", headers=otra).status_code == 404
    assert _consultar(otra, RESUELTA, conversacion_id=mia["conversacion_id"]).status_code == 404
    r = _consultar(otra, AMBIGUA, consulta_id=mia["id"], especie_id=MORADA)
    assert r.status_code == 404
    assert api.get("/conversaciones", headers=otra).json() == []


def test_el_visitante_no_guarda_conversaciones():
    token = api.post("/auth/anonimo").json()["access_token"]
    visitante = {"Authorization": f"Bearer {token}"}
    r = _consultar(visitante, AMBIGUA).json()
    assert r["estado"] == "ambigua" and r["id"] is None and r["conversacion_id"] is None
    assert api.get("/conversaciones", headers=visitante).status_code == 401
    # RR_17 sin cuenta: sigue funcionando reenviando la especie elegida.
    elegida = _consultar(visitante, AMBIGUA, especie_id=MORADA).json()
    assert elegida["estado"] == "resuelta"


def test_token_invalido_en_sesion_responde_401():
    # Así el frontend descarta el token y pide uno anónimo nuevo, en vez de
    # quedarse con un token con el que no puede consultar.
    malo = {"Authorization": "Bearer no-es-un-token"}
    assert api.get("/auth/sesion", headers=malo).status_code == 401
