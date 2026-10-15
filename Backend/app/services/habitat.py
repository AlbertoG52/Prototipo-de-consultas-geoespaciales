"""Texto de hábitat de una especie — RR_29 criterio 2.

Una pregunta de hábitat ("¿En qué tipo de bosque vive...?") se responde con los
campos de hábitat de la ficha del Manual (get_species de CR-BioLM), no con el
párrafo de distribución:

    habits         forma de crecimiento y dónde se apoya: "árbol", "epífita"...
    forest_types   tipos de bosque: "muy húmedo", "nuboso", "páramo", "roble"...
    vertientes     "Caribe", "Pacífico"
    elev_min/max   elevación en metros

    -> "Árbol o arbusto. Crece en bosque pluvial, robledal y páramo, en las
        vertientes del Caribe y del Pacífico, entre 2300 y 3600 m de elevación."

Solo junta lo que trae la ficha: no agrega nada que el Manual no diga. Sin tipo
de bosque, vertiente ni elevación devuelve None, y la respuesta usa el párrafo
de distribución como antes (services/contexto_especie.py).
"""

from __future__ import annotations

from typing import Any

# Formas de crecimiento; las demás (epífita, terrestre...) dicen dónde vive.
_FORMAS = frozenset({"árbol", "arbusto", "hierba", "bejuco", "palma", "sufrútice"})

# Cómo se nombra cada tipo de bosque del vocabulario de CR-BioLM en una frase.
_NOMBRES_DE_BOSQUE = {
    "húmedo": "bosque húmedo",
    "muy húmedo": "bosque muy húmedo",
    "nuboso": "bosque nuboso",
    "pluvial": "bosque pluvial",
    "seco": "bosque seco",
    "roble": "robledal",
}


def texto_de_habitat(ficha: dict[str, Any]) -> str | None:
    """El hábitat de la especie en una o dos frases, o None si la ficha no lo dice."""
    bosques = _tipos_de_bosque(ficha.get("forest_types"))
    lugar = [
        parte
        for parte in (
            f"en {bosques}" if bosques else "",
            _vertientes(ficha.get("vertientes")),
            _elevacion(ficha.get("elev_min"), ficha.get("elev_max")),
        )
        if parte
    ]
    if not lugar:
        return None
    crece = f"Crece {', '.join(lugar)}."
    forma = _forma(ficha.get("habits"))
    return f"{forma}. {crece}" if forma else crece


def _lista(valores: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b y c'."""
    return valores[0] if len(valores) == 1 else f"{', '.join(valores[:-1])} y {valores[-1]}"


def _forma(habitos: Any) -> str:
    """['árbol', 'arbusto'] -> 'Árbol o arbusto'; ['palma', 'terrestre'] -> 'Palma terrestre'."""
    habitos = [str(h) for h in habitos or []]
    formas = [h for h in habitos if h in _FORMAS]
    otros = [h for h in habitos if h not in _FORMAS]
    texto = " ".join([" o ".join(formas), *otros]).strip()
    return texto[:1].upper() + texto[1:]


def _tipos_de_bosque(tipos: Any) -> str:
    nombres = [_NOMBRES_DE_BOSQUE.get(str(t), str(t)) for t in tipos or []]
    return _lista(nombres) if nombres else ""


def _vertientes(vertientes: Any) -> str:
    nombres = [f"del {v}" for v in vertientes or []]
    if not nombres:
        return ""
    if len(nombres) == 1:
        return f"en la vertiente {nombres[0]}"
    return f"en las vertientes {_lista(nombres)}"


def _elevacion(minima: Any, maxima: Any) -> str:
    if minima is not None and maxima is not None:
        return f"entre {minima} y {maxima} m de elevación"
    if maxima is not None:
        return f"hasta {maxima} m de elevación"
    if minima is not None:
        return f"desde {minima} m de elevación"
    return ""
