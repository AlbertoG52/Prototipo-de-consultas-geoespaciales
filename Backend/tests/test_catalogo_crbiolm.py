"""Pruebas de CatalogoCRBioLM (services/catalogo_crbiolm.py).

Levantan un servidor MCP falso con las herramientas de CR-BioLM que usa el
catálogo (get_species, get_occurrence_points, get_species_map_image), con
sus mismas respuestas. Las que pasan por la API necesitan la BD.
"""

import base64
import socket
import threading
import time

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP

from app import config
from app.services.catalogo import obtener_catalogo
from app.services.catalogo_crbiolm import CatalogoCRBioLM, a_id, a_nombre

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
CAPAS = "CR base (provinces) | GBIF presence points (n=2, red dots)"
pedidos_de_mapa: list[str] = []


@falso.tool()
def get_species_map_image(species: str) -> dict:
    pedidos_de_mapa.append(species)
    if species == "Quercus costaricensis":
        valor = {"png_base64": base64.b64encode(PNG).decode(), "n_pts": 2, "layer_summary": CAPAS}
        return _sobre(valor, "MPCR+GBIF+DEM", "Manual + GBIF + DEM", "estimated")
    if species == "Quercus oleoides":
        return _sobre(None, confianza="insufficient", advertencia="no map")
    raise ValueError("el renderizador falló")


@falso.tool()
def get_occurrence_points(species: str, limit: int = 500) -> dict:
    cita = "GBIF occurrence API — Costa Rica"
    if species != "Quercus costaricensis":
        return _sobre({"n": 0, "truncated": False, "points": []}, "GBIF", cita, "insufficient")
    puntos = [
        {
            "lat": 9.64,
            "lon": -83.85,
            "elev_m": 2750,
            "region": "Talamanca",
            "vertiente": "Pacífico",
        },
        {"lat": 9.56, "lon": -83.75, "elev_m": None, "region": None, "vertiente": None},
    ]
    return _sobre({"n": 2, "truncated": False, "points": puntos}, "GBIF", cita)


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
    assert respuesta.total_registros == len(respuesta.registros) == 2
    assert respuesta.registros[0].localidad == "Talamanca"
    assert respuesta.registros[1].elevacion_m is None
    assert respuesta.fuentes == [
        "Manual de Plantas de Costa Rica, Tomo V, p. 779",
        "GBIF occurrence API — Costa Rica",
    ]


def test_sin_registros_de_gbif_la_respuesta_sale_sin_mapa(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-oleoides", "")
    assert respuesta.registros == [] and respuesta.total_registros == 0


def test_especie_que_no_esta_en_el_manual(crbiolm):
    assert crbiolm.construir_respuesta("especie-inventada", "") is None
    assert crbiolm.obtener_especie("especie-inventada") is None


@pytest.mark.parametrize("especie", ["quercus-costaricensis", "Quercus costaricensis"])
def test_ficha_por_id_o_por_nombre(crbiolm, especie):
    ficha = crbiolm.obtener_ficha(especie)
    assert ficha.nombre_comun == "roble negro"
    assert ficha.habitat == "montano, nuboso"
    assert ficha.descripcion == "Árbol de hasta 30 m."
    assert ficha.total_registros == 2


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
    assert len(datos["respuesta"]["registros"]) == 2


# --- mapas: todos vienen de CR-BioLM ----------------------------------------------


def test_la_respuesta_trae_el_mapa_de_cr_biolm(crbiolm):
    mapa = crbiolm.construir_respuesta("quercus-costaricensis", "").mapa
    assert mapa.url == "/especies/quercus-costaricensis/mapa"
    assert mapa.capas == ["CR base (provinces)", "GBIF presence points (n=2, red dots)"]
    assert mapa.puntos == 2
    assert crbiolm.obtener_mapa("quercus-costaricensis") == PNG


def test_el_mapa_se_guarda_en_memoria(crbiolm):
    pedidos_de_mapa.clear()
    crbiolm.construir_respuesta("quercus-costaricensis", "")
    crbiolm.obtener_mapa("quercus-costaricensis")
    crbiolm.obtener_ficha("quercus-costaricensis")
    assert pedidos_de_mapa == ["Quercus costaricensis"]


def test_si_cr_biolm_no_genera_mapa_no_hay_mapa(crbiolm):
    assert crbiolm.construir_respuesta("quercus-oleoides", "").mapa is None
    assert crbiolm.obtener_mapa("quercus-oleoides") is None


def test_si_la_herramienta_del_mapa_falla_la_respuesta_sale_sin_mapa(crbiolm):
    respuesta = crbiolm.construir_respuesta("inga-edulis", "")
    assert respuesta.texto == "Cultivada en todo el país."
    assert respuesta.mapa is None


def test_la_ficha_tambien_trae_el_mapa(crbiolm):
    assert crbiolm.obtener_ficha("quercus-costaricensis").mapa.puntos == 2


def test_el_endpoint_entrega_el_png(crbiolm, visitante):
    respuesta = api.get("/especies/quercus-costaricensis/mapa", headers=visitante)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"
    assert respuesta.content == PNG


def test_el_endpoint_sin_mapa_responde_404(crbiolm, visitante):
    assert api.get("/especies/quercus-oleoides/mapa", headers=visitante).status_code == 404


def test_el_endpoint_pide_sesion(crbiolm):
    assert api.get("/especies/quercus-costaricensis/mapa").status_code == 401


def test_el_catalogo_de_demostracion_no_tiene_mapas(visitante):
    assert api.get("/especies/guarianthe-skinneri/mapa", headers=visitante).status_code == 404
