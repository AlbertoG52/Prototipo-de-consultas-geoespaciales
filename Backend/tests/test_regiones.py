"""Pruebas de RR_39 — región o zona mencionada (services/regiones.py).

No necesitan CR-BioLM ni la BD: usan un vocabulario fijo con nombres reales del
Manual. Las que filtran los registros están en test_catalogo_crbiolm.py.
"""

import pytest

from app.services.regiones import extraer_zona

VOCABULARIO = {
    "regions": [
        "Cordillera de Talamanca",
        "Baja Talamanca",
        "Cordillera de Guanacaste",
        "Llanuras de Guanacaste",
        "Valle Central",
        "Valle Central Occidental",
        "Valle Central Oriental",
        "Valle del General",
        "Península de Osa - Golfito",
        "Fila Costeña (Norte)",
        "Fila Costeña Norte",
    ],
    "vertientes": ["Caribe", "Pacífico"],
}


def _regiones(texto: str) -> set[str] | None:
    zona = extraer_zona(texto, VOCABULARIO)
    return set(zona.regiones) if zona else None


# --- criterio 1: identifica la región o zona ----------------------------------------


@pytest.mark.parametrize(
    ("texto", "regiones"),
    [
        # nombre completo: solo esa región
        ("¿Dónde crece en la Cordillera de Talamanca?", {"cordillera de talamanca"}),
        # y sus variantes que empiezan igual
        (
            "Registros en el Valle Central",
            {"valle central", "valle central occidental", "valle central oriental"},
        ),
        # una parte de un nombre compuesto
        ("¿Hay en Golfito?", {"peninsula de osa golfito"}),
        # una palabra propia de varias regiones: todas
        ("¿Dónde crece en Talamanca?", {"cordillera de talamanca", "baja talamanca"}),
        ("en Guanacaste", {"cordillera de guanacaste", "llanuras de guanacaste"}),
        # sin tildes, mayúsculas ni signos; las variantes escritas distinto son una
        ("en la FILA COSTEÑA NORTE", {"fila costena norte"}),
        ("en el valle del general", {"valle del general"}),
    ],
)
def test_reconoce_la_region(texto, regiones):
    assert _regiones(texto) == regiones


@pytest.mark.parametrize(
    ("texto", "vertiente"), [("en el Caribe", "caribe"), ("Pacífico", "pacifico")]
)
def test_reconoce_la_vertiente(texto, vertiente):
    zona = extraer_zona(texto, VOCABULARIO)
    assert zona is not None
    assert (set(zona.regiones), zona.vertiente) == (set(), vertiente)


# --- criterio 3: sin zona, sin filtro ----------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "¿Dónde crece Quercus costaricensis?",
        "Información general de Quercus costaricensis",  # "general" sola no cuenta
        "en el valle",  # palabra genérica
        "en la zona norte del país",
        "en Cartago",  # las provincias no son regiones botánicas
        "",
    ],
)
def test_sin_region_no_hay_zona(texto):
    assert extraer_zona(texto, VOCABULARIO) is None


def test_sin_vocabulario_no_hay_zona():
    assert extraer_zona("en la Cordillera de Talamanca", None) is None


# --- qué puntos quedan dentro -------------------------------------------------------


def test_un_punto_esta_en_la_zona_por_su_region_y_su_vertiente():
    zona = extraer_zona("en Talamanca, vertiente del Caribe", VOCABULARIO)
    assert zona is not None
    caribe = {"region": "Baja Talamanca", "vertiente": "Vertiente del Caribe"}
    pacifico = {"region": "Cordillera de Talamanca", "vertiente": "Vertiente del Pacífico"}
    otra_region = {"region": "Valle Central", "vertiente": "Vertiente del Caribe"}
    assert zona.incluye(caribe)
    assert not zona.incluye(pacifico)
    assert not zona.incluye(otra_region)
    assert not zona.incluye({"region": None, "vertiente": None})
