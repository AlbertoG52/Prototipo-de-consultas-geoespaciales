"""Validación de los datos de CR-BioLM antes de armar la respuesta — RR_60 y RR_43.

Son reglas puras (no llaman a CR-BioLM): services/catalogo_crbiolm.py las
aplica a lo que recibe de cada fuente ANTES de construir la respuesta, así el
módulo de respuesta (y el frontend) nunca ven un dato que no corresponda a la
especie consultada.

RR_60 — correspondencia exacta de especie, en todas las fuentes:

    Manual (get_species)        la ficha debe ser de la especie pedida, con el
                                mismo nombre científico (sin importar mayúsculas
                                ni espacios). Si no, se descarta entera.
    GBIF (get_occurrence_points) se pide con el nombre ya validado del Manual.
                                CR-BioLM resuelve ese nombre en el backbone de
                                GBIF exigiendo coincidencia EXACTA (sin
                                coincidencias aproximadas ni de otro rango) y
                                busca por ese taxón. Aquí además se descarta
                                cada punto que no sea un registro válido en
                                Costa Rica.
    Mapa (get_species_map_image) se pide con el mismo nombre validado y solo si
                                hay registros suficientes (RR_43).

RR_43 — volumen mínimo: `alcanza_para_mapa` decide si hay registros suficientes
para generar el mapa (config.MINIMO_REGISTROS_MAPA).
"""

from __future__ import annotations

import math
from typing import Any

from .. import config

# Caja de Costa Rica (lon_min, lat_min, lon_max, lat_max): la misma con la que
# CR-BioLM limpia los puntos de GBIF (gbif_map._CR_BOX). Como allá, deja fuera
# la isla del Coco (~ -87°): si CR-BioLM la incluye, hay que cambiarla aquí también.
CAJA_COSTA_RICA = (-86.0, 7.9, -82.5, 11.3)


def normalizar_nombre(nombre: str) -> str:
    """'  Quercus   COSTARICENSIS ' -> 'quercus costaricensis'."""
    return " ".join(nombre.split()).casefold()


def misma_especie(pedida: str, recibida: Any) -> bool:
    """True si `recibida` es exactamente la especie pedida (RR_60)."""
    if not isinstance(recibida, str) or not recibida.strip():
        return False
    return normalizar_nombre(pedida) == normalizar_nombre(recibida)


def punto_valido(punto: Any) -> bool:
    """True si el punto de GBIF es un registro utilizable en Costa Rica (RR_60).

    Descarta coordenadas ausentes, no numéricas, NaN, (0, 0) y fuera de la caja
    de Costa Rica.
    """
    if not isinstance(punto, dict):
        return False
    lat, lon = _numero(punto.get("lat")), _numero(punto.get("lon"))
    if lat is None or lon is None:
        return False
    lon_min, lat_min, lon_max, lat_max = CAJA_COSTA_RICA
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def alcanza_para_mapa(registros_validos: int) -> bool:
    """RR_43: True si hay suficientes registros para generar el mapa."""
    return registros_validos >= config.MINIMO_REGISTROS_MAPA


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    return float(valor) if math.isfinite(valor) else None
