"""Pruebas de RR_22 (idioma), RR_32 (sin sentido), RR_37 (saludos y fuera de tema)
y RR_40 (ayuda): services/preprocesamiento.py y su uso en POST /consultas.

Las de la primera parte no necesitan la BD; las que pasan por la API, sí, y
borran lo que crean. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest

from app import config
from app.dominio import MotivoOrientacion
from app.main import app
from app.services import consultas, intencion
from app.services.catalogo import CatalogoDemo, obtener_catalogo
from app.services.contexto_especie import MANUAL
from app.services.preprocesamiento import (
    EJEMPLOS_DE_CONSULTA,
    fuera_de_tema,
    interpretar,
    mensaje_de,
)

from apoyo import api, crear_cuenta_verificada, sql

PASSWORD = "Clave#2024"


# --- RR_32: consultas sin sentido ---------------------------------------------------


@pytest.mark.parametrize("texto", ["asdfgh", "123", "???", "msnm", "qwrtzp lkjhg"])
def test_sin_sentido(texto):
    assert interpretar(texto) == MotivoOrientacion.SIN_SENTIDO


@pytest.mark.parametrize(
    "texto",
    ["Quercus costaricensis", "planta inventada xyz", "a", "Especies a 1500 msnm"],
)
def test_basta_una_palabra_con_sentido(texto):
    assert interpretar(texto) != MotivoOrientacion.SIN_SENTIDO


# --- RR_22: idioma ------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "Where does Quercus costaricensis grow?",
        "What is the habitat of Cedrela odorata?",
        "Show me the map of Bactris gasipaes",
    ],
)
def test_claramente_ingles_no_es_compatible(texto):
    assert interpretar(texto) == MotivoOrientacion.IDIOMA


@pytest.mark.parametrize(
    "texto",
    [
        "Quercus costaricensis",  # latín: no cuenta para ningún idioma
        "Persea americana",
        "Cedrela odorata in Guanacaste",  # una sola palabra en inglés no basta
        "¿Where crece Quercus costaricensis?",  # con "¿" ya es español
        "¿Dónde crece Quercus costaricensis?",
    ],
)
def test_ante_la_duda_la_consulta_sigue(texto):
    assert interpretar(texto) != MotivoOrientacion.IDIOMA


def test_el_mensaje_de_idioma_lo_explica_tambien_en_ingles():
    assert "only Spanish" in mensaje_de(MotivoOrientacion.IDIOMA, "")


# --- RR_40: solicitudes de ayuda ----------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "¿Qué puedo preguntar?",
        "ayuda",
        "Hola, ¿qué puedo preguntar?",
        "¿Cómo funciona?",
        "¿Qué puedo hacer con el manual de plantas?",
        "¿Qué puedo hacer aquí?",
        "¿Para qué sirve esta página?",
        "¿Qué consultas puedo hacer?",
        "¿Me puedes ayudar?",
        "Dame un ejemplo",
        "¿Quién eres?",
        "Que plantas puedo consultar del manual?",
        "Que preguntas puedo hacer sobre la flora de Costa Rica?",
        "¿Qué especies hay en el manual?",
        "¿Qué plantas conoces?",
        "help",
    ],
)
def test_reconoce_las_solicitudes_de_ayuda(texto):
    assert interpretar(texto) == MotivoOrientacion.AYUDA


@pytest.mark.parametrize(
    "texto",
    [
        "¿Para qué sirve la guaria morada?",
        "¿Cómo funciona la polinización de Quercus costaricensis?",
        "¿Cómo se usa la madera de Cedrela odorata?",
        "Ayuda con Quercus costaricensis",
        "¿Qué plantas puedo ver en Monteverde?",
        "¿Qué especies hay en Talamanca?",
    ],
)
def test_si_sobra_una_planta_es_una_consulta(texto):
    assert interpretar(texto) is None


def test_la_ayuda_explica_lo_que_admite():
    # Criterio 2: los tipos de consulta, el idioma, el largo y las fuentes.
    mensaje = mensaje_de(MotivoOrientacion.AYUDA, "ayuda")
    for parte in ("Distribución", "Hábitat", "Descripción", "español", MANUAL):
        assert parte in mensaje
    assert str(config.LONGITUD_MAXIMA_CONSULTA) in mensaje


@pytest.mark.parametrize("ejemplo", EJEMPLOS_DE_CONSULTA)
def test_los_ejemplos_son_consultas_validas(ejemplo):
    # Criterio 3: cada ejemplo pasa el preprocesamiento y reconoce una sola especie.
    assert interpretar(ejemplo) is None
    assert len(CatalogoDemo().buscar_especies(ejemplo)) == 1


# --- RR_37: saludos -----------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "hola",
        "Buenos días",
        "¡Muchas gracias!",
        "¿Qué tal todo por allá?",
        "Pura vida",
        "ok",
        "Hola, ¿cómo estás?",
        "Chao",
    ],
)
def test_reconoce_saludos_y_cortesia(texto):
    assert interpretar(texto) == MotivoOrientacion.SALUDO


@pytest.mark.parametrize(
    "texto",
    [
        "Hola, ¿dónde crece Quercus costaricensis?",
        "Gracias, ¿y Cedrela odorata?",
        "Buenos días, quiero información del cedro amargo",
    ],
)
def test_un_saludo_con_una_pregunta_es_una_consulta(texto):
    assert interpretar(texto) is None


@pytest.mark.parametrize(
    ("texto", "inicio"),
    [("hola", "¡Hola!"), ("muchas gracias", "¡Con gusto!"), ("chao", "¡Hasta pronto!")],
)
def test_el_saludo_responde_segun_lo_que_se_escribio(texto, inicio):
    mensaje = mensaje_de(MotivoOrientacion.SALUDO, texto)
    assert mensaje.startswith(inicio)
    assert "nombre común o científico" in mensaje  # criterio 2: orienta


@pytest.mark.parametrize(
    "texto",
    [
        "¿Dónde crece Quercus costaricensis?",
        "pejibaye",
        "guaria morada",
        "¿Cómo son las hojas de Cedrela odorata?",
        "Especies con elevación > 1000 msnm",
    ],
)
def test_las_consultas_normales_siguen(texto):
    assert interpretar(texto) is None


# --- RR_37: fuera de tema -----------------------------------------------------------


@pytest.mark.parametrize("texto", ["¿Quién ganó el mundial?", "información", "guaria morada"])
def test_sin_nada_sobre_plantas_esta_fuera_de_tema(texto):
    # "guaria morada" también: por eso el mensaje sugiere el nombre científico.
    assert fuera_de_tema(texto)


@pytest.mark.parametrize(
    "texto",
    ["¿Dónde crece el árbol de Navidad?", "planta inventada xyz", "¿Cómo son las hojas?"],
)
def test_con_algo_sobre_plantas_no_esta_fuera_de_tema(texto):
    assert not fuera_de_tema(texto)


def test_fuera_de_tema_incluye_las_palabras_de_habitat(monkeypatch):
    # RR_29 llena intencion.HABITAT: esas palabras también son sobre plantas.
    monkeypatch.setattr(intencion, "HABITAT", frozenset({"paramo"}))
    assert not fuera_de_tema("¿Qué hay en el páramo?")


def test_el_mensaje_fuera_de_tema_sugiere_el_nombre_cientifico():
    assert "nombre científico" in mensaje_de(MotivoOrientacion.FUERA_DE_TEMA, "")


# --- por la API ---------------------------------------------------------------------


class CatalogoQueNoSeUsa:
    """Falla si alguien lo usa: prueba que no se buscó ninguna especie."""

    def __getattr__(self, nombre):
        raise AssertionError(f"no debía buscarse en el catálogo ({nombre})")


@pytest.fixture
def visitante():
    token = api.post("/auth/anonimo").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sin_catalogo():
    app.dependency_overrides[obtener_catalogo] = CatalogoQueNoSeUsa
    yield
    app.dependency_overrides.pop(obtener_catalogo, None)


@pytest.fixture
def nuevos_tiempos():
    """Las filas de tiempos_respuesta (RR_57) creadas durante la prueba; luego las borra."""
    desde = sql("SELECT COALESCE(MAX(id), 0) FROM tiempos_respuesta").scalar()
    yield lambda: sql(
        "SELECT resultado FROM tiempos_respuesta WHERE id > :d ORDER BY id", d=desde
    ).all()
    sql("DELETE FROM tiempos_respuesta WHERE id > :d", d=desde)


def _consultar(cabeceras, texto, **extra):
    return api.post("/consultas", headers=cabeceras, json={"texto": texto, **extra})


@pytest.mark.parametrize(
    ("texto", "motivo"),
    [
        ("hola", "saludo"),
        ("¿Qué puedo preguntar?", "ayuda"),
        ("Where does Quercus costaricensis grow?", "idioma"),
        ("asdfgh", "sin_sentido"),
    ],
)
def test_se_orienta_sin_buscar_especies_y_sin_cobrar(visitante, sin_catalogo, texto, motivo):
    datos = _consultar(visitante, texto).json()
    assert datos["estado"] == "orientacion"
    assert datos["motivo"] == motivo
    assert datos["mensaje"]
    assert datos["respuesta"] is None
    assert datos["ejemplos"] == list(EJEMPLOS_DE_CONSULTA)
    assert datos["consultas_restantes"] == config.LIMITE_CONSULTAS_ANONIMO


def test_fuera_de_tema_por_la_api(visitante):
    datos = _consultar(visitante, "¿Quién ganó el mundial?").json()
    assert (datos["estado"], datos["motivo"]) == ("orientacion", "fuera_de_tema")
    assert datos["consultas_restantes"] == config.LIMITE_CONSULTAS_ANONIMO


def test_sin_especie_pero_sobre_plantas_sigue_sin_coincidencias(visitante):
    datos = _consultar(visitante, "planta inventada xyz").json()
    assert (datos["estado"], datos["motivo"]) == ("sin_coincidencias", None)
    assert datos["mensaje"] == consultas.MENSAJE_SIN_COINCIDENCIAS
    assert datos["ejemplos"] == []


def test_con_el_limite_alcanzado_se_avisa_aunque_sea_un_saludo(visitante, monkeypatch):
    monkeypatch.setattr(consultas, "limite_de", lambda identidad: 0)
    salida = _consultar(visitante, "hola")
    assert salida.status_code == 429
    assert "límite" in salida.json()["detail"]


def test_la_orientacion_queda_registrada_en_los_tiempos(visitante, nuevos_tiempos):
    _consultar(visitante, "hola")
    assert [fila.resultado for fila in nuevos_tiempos()] == ["orientacion"]


def test_con_cuenta_se_guarda_en_la_conversacion(correos_de_prueba):
    correo = correos_de_prueba()
    crear_cuenta_verificada(correo, PASSWORD)
    token = api.post("/auth/login", json={"correo": correo, "password": PASSWORD}).json()
    yo = {"Authorization": f"Bearer {token['access_token']}"}
    inicio = api.get("/auth/sesion", headers=yo).json()["consultas_restantes"]

    hola = _consultar(yo, "hola").json()
    ayuda = _consultar(yo, "¿Qué puedo preguntar?", conversacion_id=hola["conversacion_id"]).json()

    assert hola["id"] and ayuda["conversacion_id"] == hola["conversacion_id"]
    assert api.get("/auth/sesion", headers=yo).json()["consultas_restantes"] == inicio
    detalle = api.get(f"/conversaciones/{hola['conversacion_id']}", headers=yo).json()
    guardadas = detalle["consultas"]
    assert [(c["estado"], c["motivo"]) for c in guardadas] == [
        ("orientacion", "saludo"),
        ("orientacion", "ayuda"),
    ]
    assert guardadas[0]["mensaje"] == hola["mensaje"]
    assert guardadas[1]["ejemplos"] == list(EJEMPLOS_DE_CONSULTA)
