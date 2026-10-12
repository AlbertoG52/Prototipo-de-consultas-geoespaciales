"""Pruebas de CatalogoCRBioLM (services/catalogo_crbiolm.py), RR_43, RR_58 y RR_60.

Levantan un servidor MCP falso con las herramientas de CR-BioLM que usa el
catálogo (get_species, get_occurrence_points, get_species_map_image), con
sus mismas respuestas. Las que pasan por la API necesitan la BD.

Especies del servidor falso:

    Quercus costaricensis  7 puntos (1 fuera de Costa Rica) y mapa
    Inga edulis            5 puntos; la herramienta del mapa falla
    Persea americana       5 puntos; CR-BioLM no genera mapa
    Quercus oleoides       2 puntos: menos que el mínimo para un mapa (RR_43)
    Zamia fairchildiana    sin puntos
    Cedrela odorata        get_species devuelve la ficha de OTRA especie (RR_60)
"""

import base64
import socket
import threading
import time

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP

from app import config
from app.services import catalogo_crbiolm
from app.services.catalogo import obtener_catalogo
from app.services.catalogo_crbiolm import CatalogoCRBioLM, a_id, a_nombre
from app.tiempo import plazo

from apoyo import api

MANUAL = {
    "Quercus costaricensis": {
        "species": "Quercus costaricensis",
        "family": "Fagaceae",
        "elev_min": 2200,
        "elev_max": 3300,
        "forest_types": ["montano", "nuboso"],
        "common_names": ["roble negro"],
        "distribution_paragraph": "Robledales de altura de la Cordillera de Talamanca.",
        "morphology": "Árbol de hasta 30 m.",
    },
    "Inga edulis": {
        "species": "Inga edulis",
        "family": "Fabaceae",
        "common_names": [],
        "distribution_paragraph": "Cultivada en todo el país.",
    },
    "Quercus oleoides": {
        "species": "Quercus oleoides",
        "family": "Fagaceae",
        "elev_min": 0,
        "elev_max": 800,
        "common_names": [],
        "distribution_paragraph": "Bosque seco del Pacífico norte.",
    },
    "Persea americana": {"species": "Persea americana", "family": "Lauraceae"},
    "Zamia fairchildiana": {"species": "Zamia fairchildiana", "family": "Zamiaceae"},
    # RR_60: una ficha que no corresponde al nombre pedido.
    "Cedrela odorata": {"species": "Cedrela fissilis", "family": "Meliaceae"},
}

falso = FastMCP("crbiolm-falso")


def _sobre(valor, fuente="MPCR", cita="", confianza="exact", advertencia=""):
    return {
        "value": valor,
        "source": fuente,
        "citation": cita,
        "confidence": confianza,
        "caveat": advertencia,
    }


@falso.tool()
def get_species(name: str) -> dict:
    ficha = MANUAL.get(name)
    if ficha is None:
        return _sobre(None, confianza="insufficient", advertencia="not found")
    return _sobre(ficha, cita="Manual de Plantas de Costa Rica, Tomo V, p. 779")


# PNG de 1x1 que hace de mapa.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
CAPAS = "CR base (provinces) | GBIF presence points (n=6, red dots)"
pedidos_de_mapa: list[str] = []
pedidos_a_gbif: list[str] = []
# RR_58: cuántas veces más debe fallar GBIF para cada especie.
fallos_de_gbif: dict[str, int] = {}


@falso.tool()
def get_species_map_image(species: str) -> dict:
    pedidos_de_mapa.append(species)
    if species == "Quercus costaricensis":
        valor = {"png_base64": base64.b64encode(PNG).decode(), "n_pts": 6, "layer_summary": CAPAS}
        return _sobre(valor, "MPCR+GBIF+DEM", "Manual + GBIF + DEM", "estimated")
    if species == "Inga edulis":
        raise ValueError("el renderizador falló")
    return _sobre(None, confianza="insufficient", advertencia="no map")


def _puntos(cantidad: int) -> list[dict]:
    """Puntos válidos en Talamanca; el primero con todos sus datos."""
    puntos = [
        {"lat": 9.5 + i / 100, "lon": -83.7, "elev_m": None, "region": None, "vertiente": None}
        for i in range(cantidad)
    ]
    if puntos:
        puntos[0] = {
            "lat": 9.64,
            "lon": -83.85,
            "elev_m": 2750,
            "region": "Talamanca",
            "vertiente": "Pacífico",
        }
    return puntos


PUNTOS = {
    # El último está en Panamá: RR_60 lo descarta.
    "Quercus costaricensis": [*_puntos(6), {"lat": 8.9, "lon": -79.5, "elev_m": 10}],
    "Inga edulis": _puntos(5),
    "Persea americana": _puntos(5),
    "Quercus oleoides": _puntos(2),
}


@falso.tool()
def get_occurrence_points(species: str, limit: int = 500) -> dict:
    pedidos_a_gbif.append(species)
    if fallos_de_gbif.get(species, 0) > 0:
        fallos_de_gbif[species] -= 1
        raise ConnectionError("GBIF no respondió")
    cita = "GBIF occurrence API — Costa Rica"
    puntos = PUNTOS.get(species, [])
    if not puntos:
        return _sobre({"n": 0, "truncated": False, "points": []}, "GBIF", cita, "insufficient")
    return _sobre({"n": len(puntos), "truncated": False, "points": puntos}, "GBIF", cita)


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def url_falsa():
    puerto = _puerto_libre()
    servidor = uvicorn.Server(
        uvicorn.Config(
            falso.streamable_http_app(),
            host="127.0.0.1",
            port=puerto,
            log_config=None,
            log_level="warning",
        )
    )
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + 10
    while not servidor.started:
        assert time.monotonic() < limite, "el servidor MCP falso no arrancó"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{puerto}/mcp"
    servidor.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture
def crbiolm(monkeypatch, url_falsa):
    """El backend usando CATALOGO=crbiolm contra el servidor falso."""
    monkeypatch.setattr(config, "MCP_URL", url_falsa)
    monkeypatch.setattr(config, "CATALOGO", "crbiolm")
    monkeypatch.setattr(config, "MINIMO_REGISTROS_MAPA", 5)
    monkeypatch.setattr(config, "GBIF_REINTENTOS", 2)
    monkeypatch.setattr(config, "GBIF_ESPERA_REINTENTO_SEGUNDOS", 0)
    pedidos_de_mapa.clear()
    pedidos_a_gbif.clear()
    fallos_de_gbif.clear()
    return CatalogoCRBioLM()


@pytest.fixture
def visitante():
    token = api.post("/auth/anonimo").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- id <-> nombre ----------------------------------------------------------------


@pytest.mark.parametrize(
    "nombre",
    ["Quercus costaricensis", "Inga edulis var. minutula", "Cedrela odorata subsp. x"],
)
def test_el_id_se_convierte_de_ida_y_vuelta(nombre):
    especie_id = a_id(nombre)
    assert especie_id == especie_id.lower() and " " not in especie_id and "." not in especie_id
    assert a_nombre(especie_id) == nombre


# --- el catálogo --------------------------------------------------------------------


def test_obtener_catalogo_elige_segun_el_env(crbiolm):
    assert isinstance(obtener_catalogo(), CatalogoCRBioLM)


def test_reconoce_el_nombre_cientifico_dentro_de_la_pregunta(crbiolm):
    [especie] = crbiolm.buscar_especies("¿Dónde crece quercus costaricensis?")
    assert especie.id == "quercus-costaricensis"
    assert especie.nombre_cientifico == "Quercus costaricensis"
    assert especie.nombre_comun == "roble negro"


def test_dos_especies_en_la_pregunta_dan_dos_candidatas(crbiolm):
    especies = crbiolm.buscar_especies("Quercus costaricensis o Quercus oleoides")
    assert {e.nombre_cientifico for e in especies} == {"Quercus costaricensis", "Quercus oleoides"}


def test_sin_nombre_cientifico_no_reconoce_nada(crbiolm):
    # Los nombres comunes son del módulo de identificación de Jesús (RR_25).
    assert crbiolm.buscar_especies("¿Dónde crece el roble negro?") == []


def test_respuesta_con_manual_y_gbif(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert respuesta.texto.startswith("Robledales")
    assert respuesta.elevacion == "2200 – 3300 msnm"
    assert respuesta.total_registros == len(respuesta.registros) == 6
    assert respuesta.registros[0].localidad == "Talamanca"
    assert respuesta.registros[1].elevacion_m is None
    assert respuesta.avisos == []
    assert respuesta.fuentes == [
        "Manual de Plantas de Costa Rica, Tomo V, p. 779",
        "GBIF occurrence API — Costa Rica",
    ]


def test_sin_registros_de_gbif_la_respuesta_sale_sin_mapa(crbiolm):
    respuesta = crbiolm.construir_respuesta("zamia-fairchildiana", "")
    assert respuesta.registros == [] and respuesta.total_registros == 0
    assert respuesta.mapa is None
    assert respuesta.avisos == [
        "GBIF no tiene registros válidos de Zamia fairchildiana en Costa Rica, así que no hay mapa."
    ]


def test_especie_que_no_esta_en_el_manual(crbiolm):
    assert crbiolm.construir_respuesta("especie-inventada", "") is None
    assert crbiolm.obtener_especie("especie-inventada") is None


@pytest.mark.parametrize("especie", ["quercus-costaricensis", "Quercus costaricensis"])
def test_ficha_por_id_o_por_nombre(crbiolm, especie):
    ficha = crbiolm.obtener_ficha(especie)
    assert ficha.nombre_comun == "roble negro"
    assert ficha.habitat == "montano, nuboso"
    assert ficha.descripcion == "Árbol de hasta 30 m."
    assert ficha.total_registros == 6


# --- de punta a punta por la API -----------------------------------------------------


def test_consulta_ambigua_y_luego_resuelta(crbiolm, visitante):
    pregunta = "¿Quercus costaricensis o Quercus oleoides?"
    ambigua = api.post("/consultas", headers=visitante, json={"texto": pregunta})
    assert ambigua.json()["estado"] == "ambigua"

    elegida = api.post(
        "/consultas",
        headers=visitante,
        json={"texto": pregunta, "especie_id": "quercus-costaricensis"},
    )
    datos = elegida.json()
    assert datos["estado"] == "resuelta"
    assert datos["respuesta"]["especie"]["nombre_cientifico"] == "Quercus costaricensis"
    assert len(datos["respuesta"]["registros"]) == 6
    assert datos["respuesta"]["avisos"] == []


# --- mapas: todos vienen de CR-BioLM ----------------------------------------------


def test_la_respuesta_trae_el_mapa_de_cr_biolm(crbiolm):
    mapa = crbiolm.construir_respuesta("quercus-costaricensis", "").mapa
    assert mapa.url == "/especies/quercus-costaricensis/mapa"
    assert mapa.capas == ["CR base (provinces)", "GBIF presence points (n=6, red dots)"]
    assert mapa.puntos == 6
    assert crbiolm.obtener_mapa("quercus-costaricensis") == PNG


def test_el_mapa_se_guarda_en_memoria(crbiolm):
    crbiolm.construir_respuesta("quercus-costaricensis", "")
    crbiolm.obtener_mapa("quercus-costaricensis")
    crbiolm.obtener_ficha("quercus-costaricensis")
    assert pedidos_de_mapa == ["Quercus costaricensis"]


def test_si_cr_biolm_no_genera_mapa_no_hay_mapa(crbiolm):
    assert crbiolm.construir_respuesta("persea-americana", "").mapa is None
    assert crbiolm.obtener_mapa("persea-americana") is None


def test_si_la_herramienta_del_mapa_falla_la_respuesta_sale_sin_mapa(crbiolm):
    respuesta = crbiolm.construir_respuesta("inga-edulis", "")
    assert respuesta.texto == "Cultivada en todo el país."
    assert respuesta.mapa is None


def test_la_ficha_tambien_trae_el_mapa(crbiolm):
    assert crbiolm.obtener_ficha("quercus-costaricensis").mapa.puntos == 6


def test_el_endpoint_entrega_el_png(crbiolm, visitante):
    respuesta = api.get("/especies/quercus-costaricensis/mapa", headers=visitante)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"
    assert respuesta.content == PNG


def test_el_endpoint_sin_mapa_responde_404(crbiolm, visitante):
    assert api.get("/especies/persea-americana/mapa", headers=visitante).status_code == 404


def test_el_endpoint_pide_sesion(crbiolm):
    assert api.get("/especies/quercus-costaricensis/mapa").status_code == 401


def test_el_catalogo_de_demostracion_no_tiene_mapas(visitante):
    assert api.get("/especies/guarianthe-skinneri/mapa", headers=visitante).status_code == 404


# --- RR_60: correspondencia exacta de especie ----------------------------------------


def test_una_ficha_de_otra_especie_se_descarta(crbiolm):
    # Se pidió Cedrela odorata y CR-BioLM devolvió la ficha de Cedrela fissilis.
    assert crbiolm.construir_respuesta("cedrela-odorata", "") is None
    assert crbiolm.obtener_especie("cedrela-odorata") is None
    assert crbiolm.obtener_ficha("Cedrela odorata") is None
    assert crbiolm.buscar_especies("¿Dónde crece Cedrela odorata?") == []
    assert pedidos_a_gbif == [] and pedidos_de_mapa == []


def test_los_puntos_fuera_de_costa_rica_se_descartan(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert len(respuesta.registros) == respuesta.total_registros == 6  # llegaron 7
    assert all(r.longitud > -86 and r.latitud < 11.3 for r in respuesta.registros)


def test_gbif_y_el_mapa_se_piden_con_el_nombre_validado(crbiolm):
    crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert pedidos_a_gbif == pedidos_de_mapa == ["Quercus costaricensis"]


# --- RR_43: volumen mínimo para el mapa -----------------------------------------------


def test_con_menos_registros_que_el_minimo_no_hay_mapa_y_se_avisa(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-oleoides", "")
    assert respuesta.mapa is None
    assert len(respuesta.registros) == 2  # los registros sí se muestran
    assert respuesta.avisos == [
        "Solo hay 2 registros válidos de Quercus oleoides en Costa Rica y se necesitan "
        "al menos 5 para generar el mapa, así que no se muestra."
    ]
    # Criterio 3: ni siquiera se le pide el mapa a CR-BioLM.
    assert pedidos_de_mapa == []


def test_la_ficha_y_el_endpoint_tampoco_generan_mapa_con_pocos_registros(crbiolm, visitante):
    assert crbiolm.obtener_ficha("quercus-oleoides").avisos != []
    assert api.get("/especies/quercus-oleoides/mapa", headers=visitante).status_code == 404
    assert pedidos_de_mapa == []


def test_el_minimo_se_configura(crbiolm, monkeypatch):
    monkeypatch.setattr(config, "MINIMO_REGISTROS_MAPA", 7)
    assert crbiolm.construir_respuesta("quercus-costaricensis", "").mapa is None

    monkeypatch.setattr(config, "MINIMO_REGISTROS_MAPA", 2)
    crbiolm.construir_respuesta("quercus-oleoides", "")
    assert pedidos_de_mapa == ["Quercus oleoides"]


# --- RR_58: reintentos ante fallos de GBIF --------------------------------------------


def test_si_gbif_falla_una_vez_se_reintenta(crbiolm):
    fallos_de_gbif["Quercus costaricensis"] = 1
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert pedidos_a_gbif == ["Quercus costaricensis"] * 2
    assert len(respuesta.registros) == 6 and respuesta.mapa is not None
    assert respuesta.avisos == []


def test_si_todos_los_intentos_fallan_se_avisa_y_sale_el_manual(crbiolm):
    fallos_de_gbif["Quercus costaricensis"] = 99
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert len(pedidos_a_gbif) == 3  # 1 + GBIF_REINTENTOS
    assert respuesta.texto.startswith("Robledales")
    assert respuesta.registros == [] and respuesta.mapa is None
    assert respuesta.fuentes == ["Manual de Plantas de Costa Rica, Tomo V, p. 779"]
    assert respuesta.avisos == [
        "No se pudo consultar GBIF (3 intentos). La respuesta incluye solo los datos del "
        "Manual, sin registros de presencia ni mapa. Puedes intentarlo de nuevo más tarde."
    ]
    assert pedidos_de_mapa == []


def test_espera_entre_reintentos(crbiolm, monkeypatch):
    esperas: list[float] = []
    monkeypatch.setattr(catalogo_crbiolm.time, "sleep", esperas.append)
    monkeypatch.setattr(config, "GBIF_ESPERA_REINTENTO_SEGUNDOS", 1.5)
    fallos_de_gbif["Quercus costaricensis"] = 99
    crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert esperas == [1.5, 1.5]  # entre los 3 intentos, no después del último


def test_sin_reintentos_configurados_se_intenta_una_vez(crbiolm, monkeypatch):
    monkeypatch.setattr(config, "GBIF_REINTENTOS", 0)
    fallos_de_gbif["Quercus costaricensis"] = 99
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert len(pedidos_a_gbif) == 1
    assert respuesta.avisos[0].startswith("No se pudo consultar GBIF (1 intento).")


def test_no_espera_un_reintento_que_no_cabe_en_el_tiempo_de_la_consulta(crbiolm, monkeypatch):
    # RR_38: si tras la espera ya no quedaría tiempo, no se reintenta.
    esperas: list[float] = []
    monkeypatch.setattr(catalogo_crbiolm.time, "sleep", esperas.append)
    monkeypatch.setattr(config, "GBIF_ESPERA_REINTENTO_SEGUNDOS", 60)
    fallos_de_gbif["Quercus costaricensis"] = 99
    with plazo(30):
        respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert len(pedidos_a_gbif) == 1 and esperas == []
    assert respuesta.avisos[0].startswith("No se pudo consultar GBIF (1 intento).")


def test_el_aviso_llega_por_la_api(crbiolm, visitante):
    fallos_de_gbif["Quercus oleoides"] = 99
    datos = api.post(
        "/consultas",
        headers=visitante,
        json={"texto": "¿Dónde crece Quercus oleoides?"},
    ).json()
    assert datos["estado"] == "resuelta"
    assert datos["respuesta"]["avisos"][0].startswith("No se pudo consultar GBIF")
