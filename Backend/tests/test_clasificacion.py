"""Pruebas de RR_29 — clasificación del tipo de consulta (distribución, hábitat o
descripción) y el texto que elige cada tipo.

services/intencion.py, services/habitat.py y el texto de ContextoEspecie. No
necesitan la BD. El registro del tipo (criterio 3) está en
test_registro_intencion.py. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest

from app.dominio import TipoPregunta
from app.services.catalogo import CatalogoDemo
from app.services.contexto_especie import DETALLE_HABITAT, ContextoEspecie, Ocurrencias
from app.services.habitat import texto_de_habitat
from app.services.intencion import analizar, tipos_de_bosque
from app.services.mcp_cliente import Sobre

ESPECIE = "Quercus costaricensis"

# El vocabulario que da get_vocabulary de CR-BioLM (forest_types reales).
VOCABULARIO = {
    "forest_types": [
        "húmedo", "manglar", "matorral", "muy húmedo", "nuboso", "pluvial", "páramo",
        "roble", "seco",
    ]
}  # fmt: skip

# Ficha real de CR-BioLM (get_species), solo con los campos que se usan aquí.
FICHA_QUERCUS = {
    "species": ESPECIE,
    "habits": ["árbol", "arbusto"],
    "forest_types": ["pluvial", "roble", "páramo"],
    "vertientes": ["Caribe", "Pacífico"],
    "elev_min": 2300,
    "elev_max": 3600,
    "distribution_paragraph": "Robledales de altura de la Cordillera de Talamanca.",
    "morphology": "Árbol de hasta 30 m.",
}


# --- criterio 1: distribución, hábitat o descripción --------------------------------


@pytest.mark.parametrize(
    ("texto", "tipo"),
    [
        ("¿Dónde crece Quercus costaricensis?", TipoPregunta.DISTRIBUCION),
        ("¿Crece en Guanacaste?", TipoPregunta.DISTRIBUCION),
        ("¿A qué altitud vive Quercus costaricensis?", TipoPregunta.DISTRIBUCION),
        ("Mapa de Quercus costaricensis", TipoPregunta.DISTRIBUCION),
        ("¿Cuál es el hábitat de Quercus costaricensis?", TipoPregunta.HABITAT),
        ("¿En qué tipo de bosque vive Quercus costaricensis?", TipoPregunta.HABITAT),
        # "crece" junto a una palabra de hábitat pregunta por el hábitat
        ("¿En qué bosque crece Quercus costaricensis?", TipoPregunta.HABITAT),
        ("¿Se encuentra en bosque nuboso?", TipoPregunta.HABITAT),
        ("¿Es epífita?", TipoPregunta.HABITAT),
        ("¿Cómo son las hojas de Quercus costaricensis?", TipoPregunta.DESCRIPCION),
        ("¿Florece en la época seca?", TipoPregunta.DESCRIPCION),  # "seca" sola no es hábitat
        ("Quercus costaricensis", TipoPregunta.GENERAL),
        ("¿Información del roble negro?", TipoPregunta.GENERAL),  # "roble": nombre común
    ],
)
def test_clasifica_el_tipo_de_consulta(texto, tipo):
    assert analizar(texto, ESPECIE, VOCABULARIO).tipo == tipo


def test_lo_geografico_gana_si_pregunta_varias_cosas():
    texto = "¿En qué bosque y en qué provincia vive Quercus costaricensis?"
    assert analizar(texto, ESPECIE).tipo == TipoPregunta.DISTRIBUCION


def test_una_pregunta_de_habitat_sigue_siendo_geoespacial():
    # RR_41: trae GBIF y el mapa; solo cambia el texto.
    assert analizar("¿Cuál es el hábitat de Quercus costaricensis?", ESPECIE).geoespacial


@pytest.mark.parametrize("tipo", ["turbera", "ciénaga"])  # no están en la lista HABITAT
def test_los_tipos_de_bosque_de_cr_biolm_cuentan_como_habitat(tipo):
    texto = f"¿Hay Quercus costaricensis en {tipo}?"
    assert analizar(texto, ESPECIE).tipo == TipoPregunta.GENERAL  # sin vocabulario
    assert analizar(texto, ESPECIE, {"forest_types": [tipo]}).tipo == TipoPregunta.HABITAT


def test_del_vocabulario_se_descartan_las_palabras_ambiguas():
    assert tipos_de_bosque(VOCABULARIO) == {"manglar", "matorral", "nuboso", "pluvial", "paramo"}
    assert tipos_de_bosque(None) == tipos_de_bosque({}) == frozenset()


# --- criterio 2: la clasificación decide qué fuente da el texto ---------------------


def test_texto_de_habitat_con_los_campos_de_la_ficha():
    assert texto_de_habitat(FICHA_QUERCUS) == (
        "Árbol o arbusto. Crece en bosque pluvial, robledal y páramo, en las vertientes "
        "del Caribe y del Pacífico, entre 2300 y 3600 m de elevación."
    )


@pytest.mark.parametrize(
    ("ficha", "texto"),
    [
        (
            {"habits": ["palma", "terrestre"], "forest_types": ["muy húmedo"],
             "vertientes": ["Pacífico"]},
            "Palma terrestre. Crece en bosque muy húmedo, en la vertiente del Pacífico.",
        ),
        ({"elev_max": 800}, "Crece hasta 800 m de elevación."),
        ({"habits": ["árbol"]}, None),  # sin dónde vive: no hay texto de hábitat
        ({}, None),
    ],
)  # fmt: skip
def test_texto_de_habitat_solo_con_lo_que_dice_la_ficha(ficha, texto):
    assert texto_de_habitat(ficha) == texto


def _contexto(tipo: TipoPregunta, ficha: dict | None = None) -> ContextoEspecie:
    manual = Sobre(ficha or FICHA_QUERCUS, "MPCR", cita="Manual de Plantas de Costa Rica, Tomo V")
    sin_gbif = Ocurrencias(sobre=None, registros=[], total=0, intentos=1)
    return ContextoEspecie(manual, sin_gbif, None, None, [], tipo)


@pytest.mark.parametrize(
    ("tipo", "inicio"),
    [
        (TipoPregunta.HABITAT, "Árbol o arbusto. Crece en bosque pluvial"),
        (TipoPregunta.DISTRIBUCION, "Robledales de altura"),
        (TipoPregunta.DESCRIPCION, "Árbol de hasta 30 m."),
        (TipoPregunta.GENERAL, "Robledales de altura"),
    ],
)
def test_cada_tipo_responde_con_su_fuente(tipo, inicio):
    assert _contexto(tipo).texto().startswith(inicio)


def test_el_origen_del_texto_dice_que_es_el_habitat():
    # RR_45: "Origen de los datos" muestra de qué parte del Manual sale el texto.
    [texto] = [p for p in _contexto(TipoPregunta.HABITAT).procedencia() if p.dato == "texto"]
    assert DETALLE_HABITAT in texto.detalle


def test_sin_datos_de_habitat_se_usa_la_distribucion():
    ficha = {"species": ESPECIE, "distribution_paragraph": "Cordillera de Talamanca."}
    assert _contexto(TipoPregunta.HABITAT, ficha).texto() == "Cordillera de Talamanca."


def test_el_catalogo_de_demostracion_informa_el_tipo():
    demo = CatalogoDemo()
    habitat = demo.construir_respuesta("bactris-gasipaes", "¿En qué bosque vive el pejibaye?")
    general = demo.construir_respuesta("bactris-gasipaes", "pejibaye")
    assert (habitat.tipo, general.tipo) == (TipoPregunta.HABITAT, TipoPregunta.GENERAL)
