"""Pruebas de CatalogoCRBioLM (services/catalogo_crbiolm.py): RR_23, RR_24, RR_26,
RR_31, RR_39, RR_41, RR_43, RR_44, RR_45, RR_49, RR_54, RR_58 y RR_60.

Levantan un servidor MCP falso con las herramientas de CR-BioLM que usa el
catálogo (get_species, search_species, get_vocabulary, get_occurrence_points,
get_species_map_image, get_relevant_passage y answer_question), con sus mismas
respuestas. Las que pasan por la API
necesitan la BD.

Especies del servidor falso:

    Quercus costaricensis  7 puntos (1 fuera de Costa Rica) y mapa
    Inga edulis            5 puntos; la herramienta del mapa falla
    Persea americana       5 puntos; CR-BioLM no genera mapa
    Quercus oleoides       2 puntos: menos que el mínimo para un mapa (RR_43)
    Zamia fairchildiana    sin puntos
    Cedrela odorata        get_species devuelve la ficha de OTRA especie (RR_60)
    Ocotea insularis       5 puntos; el mapa llega con el nombre de OTRA especie (RR_54)
    Myrsine coriacea       la que responde el LLM (answer_question, RR_49)
    Podocarpus oleifolius  8 puntos en regiones del Manual, y mapa (RR_39)

Fragmentos del Manual (get_relevant_passage, RR_44): Quercus costaricensis tiene
uno de distribución y uno de descripción (hojas); el de Inga edulis llega con
el nombre de otra especie; las demás no tienen texto vectorizado.

answer_question (RR_49) solo responde bien preguntas sobre Myrsine coriacea; con
ciertas palabras en la pregunta simula los casos que deben usar el Manual (ver
la herramienta). Las demás preguntas no tienen respuesta del LLM.
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
from app.services.consultas import MENSAJE_SIN_COINCIDENCIAS
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
    "Ocotea insularis": {"species": "Ocotea insularis", "family": "Lauraceae"},
    "Myrsine coriacea": {
        "species": "Myrsine coriacea",
        "family": "Primulaceae",
        "common_names": [],
        "distribution_paragraph": "Bosque muy húmedo y nuboso, 800–3000 m.",
    },
    "Zamia fairchildiana": {"species": "Zamia fairchildiana", "family": "Zamiaceae"},
    "Podocarpus oleifolius": {"species": "Podocarpus oleifolius", "family": "Podocarpaceae"},
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


@falso.tool()
def get_vocabulary() -> dict:
    """Las regiones y vertientes del Manual (RR_39); aquí, unas pocas."""
    regiones = ["Cordillera de Talamanca", "Baja Talamanca", "Cordillera Central"]
    return _sobre({"regions": regiones, "vertientes": ["Caribe", "Pacífico"]})


@falso.tool()
def search_species() -> dict:
    """Sin filtros devuelve todo el catálogo (RR_23)."""
    especies = [{"species": nombre} for nombre in MANUAL]
    return _sobre({"count": len(especies), "species": especies})


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
    if species in ("Quercus costaricensis", "Podocarpus oleifolius"):
        valor = {"png_base64": base64.b64encode(PNG).decode(), "n_pts": 6, "layer_summary": CAPAS}
        return _sobre(valor, "MPCR+GBIF+DEM", "Manual + GBIF + DEM", "estimated")
    if species == "Inga edulis":
        raise ValueError("el renderizador falló")
    if species == "Ocotea insularis":  # RR_54: llega el mapa de otra especie
        valor = {"species": "Ocotea tenera", "png_base64": base64.b64encode(PNG).decode()}
        return _sobre(valor, "MPCR+GBIF+DEM", "Manual + GBIF + DEM", "estimated")
    return _sobre(None, confianza="insufficient", advertencia="no map")


PASAJE_HOJAS = "Hojas coriáceas, elípticas, con el envés pubescente."
pedidos_de_pasaje: list[str] = []
pasaje_falla = False


@falso.tool()
def get_relevant_passage(species: str, question: str, top_k: int = 1) -> dict:
    pedidos_de_pasaje.append(species)
    if pasaje_falla:
        raise RuntimeError("la base de vectores no está levantada")
    cita = "Manual de Plantas de Costa Rica, Tomo V, p. 779 — e5 embeddings"
    if species == "Quercus costaricensis":
        if "hoja" in question.lower():
            pasaje = {"section": "description", "ordinal": 0, "text": PASAJE_HOJAS}
        else:
            texto = "Robledales de altura de la Cordillera de Talamanca."
            pasaje = {"section": "distribution", "ordinal": 0, "text": texto}
        return _sobre({"species": species, "passages": [pasaje]}, cita=cita, confianza="estimated")
    if species == "Inga edulis":  # RR_60: llega el fragmento de otra especie
        pasaje = {"section": "description", "ordinal": 0, "text": "Texto de otra especie."}
        return _sobre({"species": "Inga spectabilis", "passages": [pasaje]}, cita=cita)
    return _sobre(None, confianza="insufficient", advertencia="No indexed text")


# --- RR_49: answer_question (el LLM de CR-BioLM) ------------------------------

TEXTO_IA = (
    "Myrsine coriacea crece en bosques muy húmedos y nubosos de Costa Rica, entre "
    "800 y 3000 m de altitud【Myrsine coriacea (Tomo VI, p.44)】."
)
CITA_IA = "Manual de Plantas de Costa Rica, Tomo VI, p. 44 (Myrsine coriacea)"
pedidos_a_ia: list[str] = []


def _respuesta_ia(modo: str, citas: list[str]) -> dict:
    valor = {
        "text": TEXTO_IA,
        "mode": modo,
        "constraints": {},
        "selector": None,
        "map_path": None,
        "n_pts": 0,
        "citations": citas,
    }
    return _sobre(valor, cita="Manual de Plantas de Costa Rica", confianza="estimated")


@falso.tool()
def answer_question(question: str) -> dict:
    pedidos_a_ia.append(question)
    if "sin llave" in question:
        raise ValueError("OPENROUTER_API_KEY not configured")
    if "lenta" in question:
        time.sleep(2.5)
    if "lista" in question:  # respondió con una lista de especies (modo B)
        return _respuesta_ia("B (lista)", [CITA_IA])
    if "otra especie" in question:  # citó el Manual de otra especie (RR_60)
        return _respuesta_ia(
            "A (especie)", ["Manual de Plantas de Costa Rica, Tomo VI, p. 45 (Myrsine pellucida)"]
        )
    if "Myrsine coriacea" in question:
        return _respuesta_ia("A (especie)", [CITA_IA])
    return _sobre(None, confianza="insufficient", advertencia="no answer")


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
            "date": "2019-03-14",
        }
    return puntos


def _en(region: str | None, vertiente: str | None, i: int) -> dict:
    """Un punto válido de Costa Rica en esa región (RR_39)."""
    nombre_vertiente = f"Vertiente del {vertiente}" if vertiente else None
    lat, lon = 9.6 + i / 100, -83.7
    return {"lat": lat, "lon": lon, "elev_m": 2000, "region": region, "vertiente": nombre_vertiente}


PUNTOS = {
    # El último está en Panamá: RR_60 lo descarta.
    "Quercus costaricensis": [*_puntos(6), {"lat": 8.9, "lon": -79.5, "elev_m": 10}],
    "Inga edulis": _puntos(5),
    "Persea americana": _puntos(5),
    "Ocotea insularis": _puntos(5),
    "Quercus oleoides": _puntos(2),
    # RR_39: 3 en la Cordillera de Talamanca, 2 en Baja Talamanca, 2 en la
    # Cordillera Central y 1 sin región.
    "Podocarpus oleifolius": [
        *[_en("Cordillera de Talamanca", "Pacífico", i) for i in range(3)],
        *[_en("Baja Talamanca", "Caribe", i) for i in range(2)],
        *[_en("Cordillera Central", "Caribe", i) for i in range(2)],
        _en(None, None, 0),
    ],
}
# RR_39: si no es None, CR-BioLM entrega solo estos puntos con el límite por
# defecto, como cuando una especie tiene más de 500.
corte_de_puntos: int | None = None


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
    if corte_de_puntos is not None and limit == 500:
        recortados = puntos[:corte_de_puntos]
        return _sobre({"n": len(puntos), "truncated": True, "points": recortados}, "GBIF", cita)
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
    global pasaje_falla, corte_de_puntos
    pasaje_falla = False
    corte_de_puntos = None
    pedidos_de_mapa.clear()
    pedidos_a_gbif.clear()
    pedidos_de_pasaje.clear()
    pedidos_a_ia.clear()
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


@pytest.mark.parametrize(
    "texto", ["¿Dónde crece QUERCUS COSTARICENSIS?", "¿Dónde crece Quércus costaricénsis?"]
)
def test_tildes_y_mayusculas_no_cambian_la_especie_reconocida(crbiolm, texto):
    # RR_35: los nombres científicos no llevan tildes; se quitan antes de buscar.
    [especie] = crbiolm.buscar_especies(texto)
    assert especie.id == "quercus-costaricensis"


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
    # Para el usuario: la cita del Manual y "GBIF", sin los filtros técnicos.
    assert respuesta.fuentes == ["Manual de Plantas de Costa Rica, Tomo V, p. 779", "GBIF"]


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


# --- RR_54: el mapa corresponde a la especie ------------------------------------------


def test_la_url_del_mapa_es_la_de_la_especie_de_la_respuesta(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert respuesta.mapa.url == f"/especies/{respuesta.especie.id}/mapa"


def test_un_mapa_de_otra_especie_se_descarta(crbiolm, visitante):
    # Se pidió el mapa de Ocotea insularis y llegó el de Ocotea tenera.
    assert crbiolm.construir_respuesta("ocotea-insularis", "").mapa is None
    assert crbiolm.obtener_ficha("ocotea-insularis").mapa is None
    assert crbiolm.obtener_mapa("ocotea-insularis") is None
    assert api.get("/especies/ocotea-insularis/mapa", headers=visitante).status_code == 404


def test_un_mapa_que_dice_ser_de_la_especie_pedida_se_acepta():
    valor = {"species": "Quercus_costaricensis", "png_base64": "x"}
    assert catalogo_crbiolm._mapa_de_la_especie("Quercus costaricensis", valor)
    assert catalogo_crbiolm._mapa_de_la_especie("Quercus costaricensis", {"png_base64": "x"})
    assert not catalogo_crbiolm._mapa_de_la_especie("Quercus costaricensis", {"species": 3})


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


# --- RR_41: el tipo de pregunta elige el texto; GBIF y mapa vienen siempre ----------

HOJAS = "¿Cómo son las hojas de Quercus costaricensis?"


def test_una_consulta_descriptiva_tambien_trae_registros_y_mapa(crbiolm):
    # RR_52 criterio 3, RR_46 criterio 1 y RR_59: si hay datos, se muestran.
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", HOJAS)
    assert respuesta.geoespacial is False  # RR_41: la pregunta no es geográfica
    assert pedidos_a_gbif == pedidos_de_mapa == ["Quercus costaricensis"]
    assert len(respuesta.registros) == 6 and respuesta.mapa is not None


def test_una_consulta_geoespacial_pide_gbif_y_mapa(crbiolm):
    respuesta = crbiolm.construir_respuesta(
        "quercus-costaricensis", "¿Dónde crece Quercus costaricensis?"
    )
    assert respuesta.geoespacial is True
    assert pedidos_a_gbif == pedidos_de_mapa == ["Quercus costaricensis"]
    assert len(respuesta.registros) == 6 and respuesta.mapa is not None


def test_solo_el_nombre_trae_todo(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "Quercus costaricensis")
    assert respuesta.geoespacial and respuesta.mapa is not None


def test_la_ficha_siempre_trae_registros_y_mapa(crbiolm):
    ficha = crbiolm.obtener_ficha("quercus-costaricensis")
    assert ficha.total_registros == 6 and ficha.mapa is not None


# --- RR_44: el fragmento del Manual que responde la pregunta -----------------------


def test_el_texto_es_el_fragmento_que_responde_la_pregunta(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", HOJAS)
    assert respuesta.texto == PASAJE_HOJAS
    assert pedidos_de_pasaje == ["Quercus costaricensis"]  # filtrado por la especie


def test_sin_pregunta_concreta_no_se_busca_fragmento(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "Quercus costaricensis")
    assert pedidos_de_pasaje == []
    assert respuesta.texto.startswith("Robledales")


def test_un_fragmento_de_otra_especie_se_descarta(crbiolm):
    respuesta = crbiolm.construir_respuesta("inga-edulis", "¿Dónde crece Inga edulis?")
    assert pedidos_de_pasaje == ["Inga edulis"]
    assert respuesta.texto == "Cultivada en todo el país."  # el texto de la ficha


def test_si_la_herramienta_falla_se_usa_el_texto_de_la_ficha(crbiolm):
    global pasaje_falla
    pasaje_falla = True
    respuesta = crbiolm.construir_respuesta(
        "quercus-costaricensis", "¿Dónde crece Quercus costaricensis?"
    )
    assert respuesta.texto.startswith("Robledales")
    assert respuesta.mapa is not None  # lo demás sale igual


def test_sin_fragmento_una_pregunta_descriptiva_usa_la_morfologia(crbiolm):
    global pasaje_falla
    pasaje_falla = True
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", HOJAS)
    assert respuesta.texto == "Árbol de hasta 30 m."


def test_sin_texto_vectorizado_se_usa_la_distribucion(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-oleoides", "¿Cómo son sus flores?")
    assert pedidos_de_pasaje == ["Quercus oleoides"]
    assert respuesta.texto == "Bosque seco del Pacífico norte."


# --- RR_45: contexto único y procedencia de cada dato -------------------------------


def _origen(respuesta) -> dict[str, tuple[str, str]]:
    return {p.dato: (p.fuente, p.detalle) for p in respuesta.procedencia}


def test_cada_dato_dice_de_donde_sale(crbiolm):
    respuesta = crbiolm.construir_respuesta(
        "quercus-costaricensis", "¿Dónde crece Quercus costaricensis?"
    )
    origen = _origen(respuesta)
    assert set(origen) == {"especie", "texto", "elevacion", "registros", "mapa"}
    assert origen["especie"] == ("Manual de Plantas de Costa Rica", "Tomo V, p. 779")
    assert origen["texto"] == (
        "Manual de Plantas de Costa Rica",
        "Tomo V, p. 779 · distribución · fragmento más relacionado con la pregunta",
    )
    assert origen["elevacion"] == ("Manual de Plantas de Costa Rica", "Tomo V, p. 779")
    assert origen["registros"] == (
        "GBIF",
        "registros de presencia en Costa Rica, consultados en vivo",
    )
    assert origen["mapa"] == (
        "CR-BioLM",
        "elaborado con las regiones botánicas de M. V. Castro (Manual de Plantas de "
        "Costa Rica), las áreas silvestres protegidas del SINAC, la altitud de SRTM e "
        "INEC y los registros de GBIF",
    )


def test_el_origen_no_muestra_detalles_tecnicos(crbiolm):
    # Las citas técnicas de CR-BioLM (filtros de GBIF, archivos del mapa) no se
    # muestran al usuario, ni en la pantalla ni en la descarga.
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    textos = [p.detalle for p in respuesta.procedencia] + respuesta.fuentes
    for tecnico in ("occurrence API", "Manual + GBIF + DEM", "ficha estructurada"):
        assert not any(tecnico in t for t in textos)


def test_el_texto_dice_si_salio_de_la_busqueda_semantica_o_de_la_ficha(crbiolm):
    con_fragmento = crbiolm.construir_respuesta("quercus-costaricensis", HOJAS)
    assert _origen(con_fragmento)["texto"][1].endswith(
        "descripción · fragmento más relacionado con la pregunta"
    )
    sin_fragmento = crbiolm.construir_respuesta("quercus-costaricensis", "Quercus costaricensis")
    assert _origen(sin_fragmento)["texto"][1] == "Tomo V, p. 779 · distribución"


def test_sin_gbif_ni_mapa_no_se_indica_su_origen(crbiolm):
    fallos_de_gbif["Quercus costaricensis"] = 99
    sin_gbif = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert "registros" not in _origen(sin_gbif) and "mapa" not in _origen(sin_gbif)


def test_la_ficha_tambien_trae_la_procedencia(crbiolm):
    origen = _origen(crbiolm.obtener_ficha("quercus-costaricensis"))
    assert set(origen) == {"especie", "elevacion", "registros", "mapa"}  # la ficha no tiene texto


def test_el_contexto_junta_las_fuentes_de_la_especie(crbiolm):
    contexto = crbiolm.contexto("Quercus costaricensis", HOJAS)
    assert contexto.especie == "Quercus costaricensis"
    assert contexto.fragmento.texto == PASAJE_HOJAS  # fuente vectorizada
    assert contexto.ficha["family"] == "Fagaceae"  # fuente estructurada
    assert contexto.total_registros == 6  # GBIF
    assert contexto.tipo == "descripcion" and not contexto.geoespacial


def test_la_procedencia_llega_por_la_api(crbiolm, visitante):
    datos = api.post("/consultas", headers=visitante, json={"texto": HOJAS}).json()
    respuesta = datos["respuesta"]
    assert respuesta["geoespacial"] is False
    assert respuesta["texto"] == PASAJE_HOJAS
    assert {p["dato"] for p in respuesta["procedencia"]} == {
        "especie",
        "texto",
        "elevacion",
        "registros",
        "mapa",
    }


# --- RR_49: respuesta redactada por el LLM de CR-BioLM --------------------------

DONDE_MYRSINE = "¿Dónde crece Myrsine coriacea?"
TEXTO_MANUAL_MYRSINE = "Bosque muy húmedo y nuboso, 800–3000 m."


def test_la_respuesta_usa_el_texto_redactado_por_el_llm(crbiolm):
    respuesta = crbiolm.construir_respuesta("myrsine-coriacea", DONDE_MYRSINE)
    assert pedidos_a_ia == [DONDE_MYRSINE]
    assert respuesta.texto == TEXTO_IA
    assert _origen(respuesta)["texto"] == (
        "Manual de Plantas de Costa Rica",
        "Tomo V, p. 779 · respuesta redactada con IA a partir del Manual",
    )
    # RR_50: la página que citó el LLM también aparece entre las fuentes.
    assert "Manual de Plantas de Costa Rica, Tomo VI, p. 44" in respuesta.fuentes


def test_sin_pregunta_no_se_le_pide_nada_al_llm(crbiolm):
    respuesta = crbiolm.construir_respuesta("myrsine-coriacea", "")
    assert pedidos_a_ia == []
    assert respuesta.texto == TEXTO_MANUAL_MYRSINE


def test_la_ficha_no_usa_el_llm(crbiolm):
    crbiolm.obtener_ficha("myrsine-coriacea")
    assert pedidos_a_ia == []


@pytest.mark.parametrize(
    "caso",
    [
        "sin llave",  # la herramienta falla (p. ej. sin OPENROUTER_API_KEY)
        "lista",  # respondió una lista de especies, no sobre la pedida
        "otra especie",  # sus citas son de otra especie (RR_60)
    ],
)
def test_si_el_llm_no_sirve_se_usa_el_texto_del_manual(crbiolm, caso):
    respuesta = crbiolm.construir_respuesta("myrsine-coriacea", f"{DONDE_MYRSINE} ({caso})")
    assert len(pedidos_a_ia) == 1
    assert respuesta.texto == TEXTO_MANUAL_MYRSINE
    assert "IA" not in _origen(respuesta)["texto"][1]


def test_si_el_llm_tarda_demasiado_se_usa_el_manual_sin_cortar_la_consulta(crbiolm, monkeypatch):
    monkeypatch.setattr(config, "SEGUNDOS_MAXIMOS_REDACCION_IA", 1)
    with plazo(60):
        respuesta = crbiolm.construir_respuesta("myrsine-coriacea", f"{DONDE_MYRSINE} (lenta)")
    assert respuesta.texto == TEXTO_MANUAL_MYRSINE


def test_sin_tiempo_en_la_consulta_no_se_pide_al_llm(crbiolm):
    with plazo(catalogo_crbiolm.MARGEN_TRAS_REDACCION + 0.5):
        respuesta = crbiolm.construir_respuesta("myrsine-coriacea", DONDE_MYRSINE)
    assert pedidos_a_ia == []
    assert respuesta.texto == TEXTO_MANUAL_MYRSINE


def test_otras_especies_siguen_con_el_texto_del_manual(crbiolm):
    # Para Quercus costaricensis el LLM falso no responde: queda el fragmento (RR_44).
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", HOJAS)
    assert respuesta.texto == PASAJE_HOJAS


def test_la_respuesta_del_llm_llega_por_la_api(crbiolm, visitante):
    datos = api.post("/consultas", headers=visitante, json={"texto": DONDE_MYRSINE}).json()
    assert datos["estado"] == "resuelta"
    assert datos["respuesta"]["texto"] == TEXTO_IA


# --- RR_23: corrección de errores ortográficos ------------------------------------
# La regla está probada en test_correccion.py; aquí, que el catálogo la aplica.


@pytest.mark.parametrize(
    "texto", ["¿Dónde crece Querus costaricensis?", "¿Dónde crece Qercus costarisensis?"]
)
def test_un_nombre_mal_escrito_se_reconoce(crbiolm, texto):
    [especie] = crbiolm.buscar_especies(texto)
    assert especie.id == "quercus-costaricensis"


def test_con_tres_letras_mal_no_se_reconoce(crbiolm):
    assert crbiolm.buscar_especies("¿Dónde crece Qercus kostarisensis?") == []


def test_el_llm_recibe_la_pregunta_con_el_nombre_corregido(crbiolm):
    """Criterio 3: la corrección se aplica antes de buscar, también para el LLM."""
    respuesta = crbiolm.construir_respuesta("myrsine-coriacea", "¿Dónde crece Myrsine coriacia?")
    assert pedidos_a_ia == [DONDE_MYRSINE]
    assert respuesta.texto == TEXTO_IA


def test_la_consulta_conserva_lo_que_escribio_el_usuario(crbiolm, visitante):
    """Criterio 2: se busca con el nombre corregido, pero el texto no cambia."""
    texto = "¿Dónde crece Querus costaricensis?"
    datos = api.post("/consultas", headers=visitante, json={"texto": texto}).json()
    assert datos["estado"] == "resuelta"
    assert datos["texto"] == texto
    assert datos["respuesta"]["especie"]["id"] == "quercus-costaricensis"


# --- RR_24: interpretación de la consulta -----------------------------------------
# La interpreta services/intencion.py (tipo de pregunta, también RR_41); aquí se
# prueba de punta a punta que lo que se entiende decide lo que se busca.


def test_una_pregunta_sobre_una_planta_se_interpreta_y_se_responde(crbiolm, visitante):
    """Criterio 1."""
    datos = api.post("/consultas", headers=visitante, json={"texto": HOJAS}).json()
    assert datos["estado"] == "resuelta"
    assert datos["respuesta"]["especie"]["nombre_cientifico"] == "Quercus costaricensis"


@pytest.mark.parametrize(
    ("pregunta", "texto", "geoespacial"),
    [
        (HOJAS, PASAJE_HOJAS, False),  # cómo es: el fragmento de la descripción
        (
            "¿Dónde crece Quercus costaricensis?",  # dónde: el de la distribución
            "Robledales de altura de la Cordillera de Talamanca.",
            True,
        ),
    ],
)
def test_lo_que_pide_la_consulta_decide_lo_que_se_busca(crbiolm, pregunta, texto, geoespacial):
    """Criterios 2 y 3: se identifica qué pide y se busca eso en el Manual de la especie."""
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", pregunta)
    assert respuesta.geoespacial is geoespacial
    assert respuesta.texto == texto
    assert pedidos_de_pasaje == ["Quercus costaricensis"]


def test_sin_pregunta_concreta_se_entrega_la_informacion_general(crbiolm):
    """Criterio 3: si solo nombra la especie, no se busca un fragmento en particular."""
    respuesta = crbiolm.construir_respuesta(
        "quercus-costaricensis", "Información sobre Quercus costaricensis"
    )
    assert pedidos_de_pasaje == []
    assert respuesta.texto.startswith("Robledales")


# --- RR_26: identificación de nombres científicos --------------------------------


def test_el_nombre_cientifico_se_asocia_con_su_especie_del_manual(crbiolm):
    """Criterios 1 y 3: la especie y sus datos salen del Manual (get_species)."""
    [especie] = crbiolm.buscar_especies("Información sobre Quercus oleoides")
    assert especie.id == "quercus-oleoides"
    assert especie.nombre_cientifico == "Quercus oleoides"
    assert especie.familia == "Fagaceae"


def test_el_mismo_genero_con_otra_especie_es_otra_especie(crbiolm):
    """Criterio 2: el género solo no basta, cuenta también el epíteto."""
    [una] = crbiolm.buscar_especies("¿Dónde crece Quercus costaricensis?")
    [otra] = crbiolm.buscar_especies("¿Dónde crece Quercus oleoides?")
    assert (una.id, otra.id) == ("quercus-costaricensis", "quercus-oleoides")


@pytest.mark.parametrize(
    "texto",
    ["¿Dónde crece Quercus?", "¿Dónde crece costaricensis?", "costaricensis Quercus"],
)
def test_el_genero_o_la_especie_solos_no_identifican_una_especie(crbiolm, texto):
    """Criterio 2: el nombre es género y luego especie; uno solo no se confunde con otra."""
    assert crbiolm.buscar_especies(texto) == []


# --- RR_31: validación de contenido reconocible ----------------------------------


@pytest.mark.parametrize(
    ("texto", "estado", "motivo"),
    [
        ("¿Dónde crece el árbol de Navidad?", "sin_coincidencias", None),
        # RR_32 y RR_37 (services/preprocesamiento.py): se rechazan igual, pero
        # orientando al usuario según lo que escribió.
        ("asdfgh", "orientacion", "sin_sentido"),
        ("¿Qué tal todo por allá?", "orientacion", "saludo"),
    ],
)
def test_sin_ningun_termino_reconocible_se_rechaza_con_el_motivo(
    crbiolm, visitante, texto, estado, motivo
):
    datos = api.post("/consultas", headers=visitante, json={"texto": texto}).json()
    assert datos["estado"] == estado  # criterio 2: se rechaza
    assert datos["motivo"] == motivo
    assert datos["respuesta"] is None
    assert datos["mensaje"]  # criterio 3: dice por qué
    if estado == "sin_coincidencias":
        assert datos["mensaje"] == MENSAJE_SIN_COINCIDENCIAS
    assert datos["consultas_restantes"] == config.LIMITE_CONSULTAS_ANONIMO  # no cuesta
    assert pedidos_a_gbif == pedidos_de_mapa == pedidos_a_ia == []  # no se busca nada


def test_con_un_termino_reconocible_la_consulta_sigue(crbiolm, visitante):
    """Criterio 1."""
    datos = api.post("/consultas", headers=visitante, json={"texto": "Quercus costaricensis"})
    assert datos.json()["estado"] == "resuelta"


# --- RR_39: región o zona mencionada ----------------------------------------------
# Qué zona se reconoce está probado en test_regiones.py; aquí, que filtra.

PODOCARPUS = "podocarpus-oleifolius"


def _registros_en(crbiolm, pregunta: str) -> tuple[int, set[str]]:
    respuesta = crbiolm.construir_respuesta(PODOCARPUS, pregunta)
    assert respuesta.total_registros == len(respuesta.registros)
    return respuesta.total_registros, {r.localidad for r in respuesta.registros}


@pytest.mark.parametrize(
    ("donde", "total", "regiones"),
    [
        ("en la Cordillera de Talamanca", 3, {"Cordillera de Talamanca"}),
        ("en Talamanca", 5, {"Cordillera de Talamanca", "Baja Talamanca"}),
        ("en el Caribe", 4, {"Baja Talamanca", "Cordillera Central"}),
    ],
)
def test_la_zona_filtra_los_registros_y_su_conteo(crbiolm, donde, total, regiones):
    """Criterios 1 y 2."""
    pregunta = f"¿Dónde crece Podocarpus oleifolius {donde}?"
    assert _registros_en(crbiolm, pregunta) == (total, regiones)


def test_sin_zona_no_se_filtra(crbiolm):
    """Criterio 3."""
    total, _ = _registros_en(crbiolm, "¿Dónde crece Podocarpus oleifolius?")
    assert total == 8


def test_el_mapa_sigue_siendo_el_nacional(crbiolm):
    # La Cordillera Central tiene 2 registros, menos que el mínimo para un mapa
    # (RR_43); el mapa se decide con los 8 del país y no hay aviso.
    respuesta = crbiolm.construir_respuesta(
        PODOCARPUS, "¿Dónde crece Podocarpus oleifolius en la Cordillera Central?"
    )
    assert respuesta.total_registros == 2
    assert respuesta.mapa is not None
    assert respuesta.avisos == []


def test_si_cr_biolm_corta_los_puntos_se_piden_todos(crbiolm):
    global corte_de_puntos
    corte_de_puntos = 4  # con el límite por defecto llegan solo 4 de 8
    total, _ = _registros_en(crbiolm, "¿Dónde crece Podocarpus oleifolius en el Caribe?")
    assert total == 4
    assert pedidos_a_gbif == ["Podocarpus oleifolius", "Podocarpus oleifolius"]


def test_la_ficha_no_se_filtra(crbiolm):
    assert crbiolm.obtener_ficha(PODOCARPUS).total_registros == 8


def test_sin_vocabulario_no_se_filtra(crbiolm, monkeypatch):
    monkeypatch.setattr(crbiolm, "_vocabulario", lambda: None)
    total, _ = _registros_en(crbiolm, "¿Dónde crece Podocarpus oleifolius en Talamanca?")
    assert total == 8


def test_la_consulta_filtra_por_zona(crbiolm, visitante):
    texto = "¿Dónde crece Podocarpus oleifolius en la Cordillera de Talamanca?"
    datos = api.post("/consultas", headers=visitante, json={"texto": texto}).json()
    assert datos["estado"] == "resuelta"
    assert datos["texto"] == texto
    assert datos["respuesta"]["total_registros"] == 3


def test_el_registro_trae_la_fecha_de_gbif(crbiolm):
    respuesta = crbiolm.construir_respuesta("quercus-costaricensis", "")
    assert respuesta.registros[0].fecha == "2019-03-14"
    assert respuesta.registros[1].fecha == "Sin dato"  # sin fecha en GBIF


@pytest.mark.parametrize(
    ("fecha", "esperada"),
    [
        ("2019-03-14T10:00:00", "2019-03-14"),
        ("2001-03/2001-04", "2001-03"),
        ("1998", "1998"),
        ("", "Sin dato"),
        (None, "Sin dato"),
    ],
)
def test_formato_de_la_fecha(fecha, esperada):
    assert catalogo_crbiolm._fecha({"date": fecha}) == esperada


# --- RR_29: clasificación del tipo de consulta ------------------------------------------


def test_una_pregunta_de_habitat_se_responde_con_el_habitat_de_la_ficha(crbiolm):
    """Criterio 2. Quercus oleoides no tiene fragmento ni respuesta del LLM en el falso."""
    respuesta = crbiolm.construir_respuesta(
        "quercus-oleoides", "¿En qué tipo de bosque vive Quercus oleoides?"
    )
    assert respuesta.tipo == "habitat"
    assert respuesta.texto == "Crece entre 0 y 800 m de elevación."
    assert respuesta.registros  # RR_41: GBIF se sigue pidiendo


def test_el_tipo_usa_los_tipos_de_bosque_del_vocabulario(crbiolm, monkeypatch):
    pregunta = "¿Hay Quercus oleoides en turbera?"
    sin_vocabulario = crbiolm.construir_respuesta("quercus-oleoides", pregunta)
    monkeypatch.setattr(crbiolm, "_vocabulario", lambda: {"forest_types": ["turbera"]})
    con_vocabulario = crbiolm.construir_respuesta("quercus-oleoides", pregunta)
    assert (sin_vocabulario.tipo, con_vocabulario.tipo) == ("general", "habitat")


# --- RR_35: CR-BioLM recibe el nombre como en el catálogo -----------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "¿Dónde crece myrsine coriacea?",
        "¿DÓNDE CRECE MYRSINE CORIACEA?",
        "¿Dónde crece Mýrsine coriácea?",
    ],
)
def test_el_llm_recibe_el_nombre_como_en_el_catalogo(crbiolm, texto):
    """Criterio 3: sin esto, CR-BioLM no reconoce la especie y el LLM no responde."""
    respuesta = crbiolm.construir_respuesta("myrsine-coriacea", texto)
    [pregunta] = pedidos_a_ia
    assert "Myrsine coriacea" in pregunta
    assert respuesta.texto == TEXTO_IA


def test_la_persona_sigue_viendo_lo_que_escribio(crbiolm, visitante):
    texto = "¿DÓNDE CRECE MYRSINE CORIÁCEA?"
    datos = api.post("/consultas", headers=visitante, json={"texto": texto}).json()
    assert datos["estado"] == "resuelta"
    assert datos["texto"] == texto  # lo guardado y mostrado no cambia
    assert datos["respuesta"]["texto"] == TEXTO_IA
