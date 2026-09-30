"""Catálogo de especies — FUENTE DE DATOS PROVISIONAL.

Los módulos 2 y 3 (interpretación de consultas y recuperación de información)
no son parte de este sprint, y el catálogo real llegará desde la API de
CR-BioLM, cuyo contrato todavía no está congelado. Sin embargo, RR_17
(selección de especie ante múltiples coincidencias) y RR_18 (alternancia entre
mapa y lista de registros) necesitan datos para que su LÓGICA exista y se
pueda probar.

La solución es esta: el resto del sistema —routers, esquemas, frontend— está
escrito contra las funciones de abajo y es código definitivo. Lo único
provisional son los datos y la forma de emparejarlos. Cuando llegue la API de
CR-BioLM se reescribe SOLO este archivo, respetando las dos funciones
públicas, y nada más del proyecto cambia.

Las funciones que hay que mantener:

    buscar_especies(texto)            -> list[EspecieCandidata]
    construir_respuesta(especie, texto) -> RespuestaConsulta
    obtener_ficha(especie)            -> FichaEspecie   (RR_20)

Los datos de abajo son ilustrativos y sirven para probar los tres caminos de
una consulta: coincidencia única, coincidencia múltiple y sin coincidencias.
No deben citarse como información científica.
"""
from __future__ import annotations

import unicodedata

from ..schemas.consulta import EspecieCandidata, FichaEspecie, RegistroPresencia, RespuestaConsulta

# --- datos provisionales ----------------------------------------------------
# 'alias' son los términos que hacen que una consulta apunte a esta especie.
# Hay dos pares que comparten alias a propósito ("guaria", "cedro") para poder
# ejercitar el camino de coincidencia múltiple de RR_17.
_CATALOGO: list[dict] = [
    {
        "id": "guarianthe-skinneri",
        "nombre_comun": "Guaria morada",
        "nombre_cientifico": "Guarianthe skinneri",
        "familia": "Orchidaceae",
        "alias": ["guaria", "guaria morada", "guarianthe skinneri"],
        "habitat": "Bosque húmedo premontano; crece como epífita sobre troncos y ramas.",
        "elevacion": "800 – 1600 msnm",
        "texto": (
            "Guarianthe skinneri es una orquídea epífita de bosque húmedo "
            "tropical. En Costa Rica se registra principalmente en el Valle "
            "Central y las estribaciones de Alajuela y Cartago, entre los 800 "
            "y los 1600 metros sobre el nivel del mar."
        ),
        "registros": [
            ("Alajuela, Valle Central", "12 mar 2024", 10.0162, -84.2133, 1240),
            ("Cartago, Turrialba", "08 ene 2024", 9.9014, -83.6800, 980),
            ("San José, Escazú", "22 nov 2023", 9.9281, -84.1363, 1100),
            ("Heredia, Barva", "05 oct 2023", 10.0726, -84.1099, 1380),
        ],
    },
    {
        "id": "guarianthe-aurantiaca",
        "nombre_comun": "Guaria naranja",
        "nombre_cientifico": "Guarianthe aurantiaca",
        "familia": "Orchidaceae",
        "alias": ["guaria", "guaria naranja", "guarianthe aurantiaca"],
        "habitat": "Bosque estacionalmente seco; epífita o sobre rocas.",
        "elevacion": "300 – 1200 msnm",
        "texto": (
            "Guarianthe aurantiaca es una orquídea de flores anaranjadas "
            "asociada a bosques estacionalmente secos. Sus registros en Costa "
            "Rica se concentran en la vertiente del Pacífico norte."
        ),
        "registros": [
            ("Guanacaste, Nicoya", "19 abr 2024", 10.1483, -85.4520, 320),
            ("Guanacaste, Liberia", "03 feb 2024", 10.6333, -85.4375, 410),
        ],
    },
    {
        "id": "cedrela-odorata",
        "nombre_comun": "Cedro amargo",
        "nombre_cientifico": "Cedrela odorata",
        "familia": "Meliaceae",
        "alias": ["cedro", "cedro amargo", "cedrela odorata"],
        "habitat": "Bosque húmedo y seco de tierras bajas y premontano.",
        "elevacion": "0 – 1200 msnm",
        "texto": (
            "Cedrela odorata es un árbol caducifolio de amplia distribución en "
            "el país, presente tanto en la vertiente del Pacífico como en la "
            "del Caribe, desde el nivel del mar hasta unos 1200 metros."
        ),
        "registros": [
            ("Puntarenas, Osa", "27 may 2024", 8.5500, -83.4667, 60),
            ("Limón, Talamanca", "14 mar 2024", 9.5667, -82.8333, 120),
            ("Guanacaste, Santa Cruz", "02 feb 2024", 10.2600, -85.5850, 210),
        ],
    },
    {
        "id": "cedrela-tonduzii",
        "nombre_comun": "Cedro dulce",
        "nombre_cientifico": "Cedrela tonduzii",
        "familia": "Meliaceae",
        "alias": ["cedro", "cedro dulce", "cedrela tonduzii"],
        "habitat": "Bosque montano de las cordilleras centrales y de Talamanca.",
        "elevacion": "1200 – 2800 msnm",
        "texto": (
            "Cedrela tonduzii ocupa el bosque montano de las cordilleras "
            "centrales y de Talamanca, en elevaciones superiores a las de su "
            "congénere Cedrela odorata."
        ),
        "registros": [
            ("Cartago, Cerro de la Muerte", "08 jun 2024", 9.5600, -83.7550, 2650),
            ("San José, Dota", "21 mar 2024", 9.6450, -83.9200, 2100),
        ],
    },
    {
        "id": "quercus-costaricensis",
        "nombre_comun": "Roble negro",
        "nombre_cientifico": "Quercus costaricensis",
        "familia": "Fagaceae",
        "alias": ["roble", "roble negro", "quercus costaricensis"],
        "habitat": "Robledal de altura (bosque montano y subalpino).",
        "elevacion": "2200 – 3300 msnm",
        "texto": (
            "Quercus costaricensis domina el robledal de altura de la "
            "cordillera de Talamanca, donde forma rodales casi puros por "
            "encima de los 2200 metros."
        ),
        "registros": [
            ("Cartago, Parque Nacional Los Quetzales", "11 jul 2024", 9.6383, -83.8500, 2750),
            ("San José, Cerro de la Muerte", "29 abr 2024", 9.5600, -83.7550, 3100),
        ],
    },
    {
        "id": "bactris-gasipaes",
        "nombre_comun": "Pejibaye",
        "nombre_cientifico": "Bactris gasipaes",
        "familia": "Arecaceae",
        "alias": ["pejibaye", "pejivalle", "bactris gasipaes"],
        "habitat": "Tierras bajas húmedas; cultivada en fincas y huertos.",
        "elevacion": "0 – 1200 msnm",
        "texto": (
            "Bactris gasipaes es una palma cultivada desde tiempos "
            "precolombinos por su fruto. En Costa Rica se encuentra sobre todo "
            "en las zonas bajas del Caribe y del Pacífico sur."
        ),
        "registros": [
            ("Limón, Guápiles", "16 may 2024", 10.2167, -83.7833, 260),
            ("Puntarenas, Golfito", "30 ene 2024", 8.6333, -83.1667, 40),
        ],
    },
]

_FUENTES = ["GBIF", "Manual de Plantas de CR"]


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas y quita acentos, para que 'Guaría' encuentre 'guaria'."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


def _a_candidata(entrada: dict) -> EspecieCandidata:
    return EspecieCandidata(
        id=entrada["id"],
        nombre_comun=entrada["nombre_comun"],
        nombre_cientifico=entrada["nombre_cientifico"],
        familia=entrada["familia"],
    )


def _registros(entrada: dict) -> list[RegistroPresencia]:
    return [
        RegistroPresencia(
            localidad=localidad,
            fecha=fecha,
            latitud=lat,
            longitud=lon,
            elevacion_m=elev,
            fuente="GBIF",
        )
        for localidad, fecha, lat, lon, elev in entrada["registros"]
    ]


def buscar_especies(texto: str) -> list[EspecieCandidata]:
    """Devuelve las especies que la consulta podría estar mencionando.

    Cero resultados significa que no se reconoció ninguna especie; más de uno
    significa que la consulta es ambigua y hay que preguntarle al usuario
    (RR_17).
    """
    consulta = _normalizar(texto)
    encontradas: list[EspecieCandidata] = []

    for entrada in _CATALOGO:
        if any(_normalizar(alias) in consulta for alias in entrada["alias"]):
            encontradas.append(_a_candidata(entrada))

    return encontradas


def obtener_especie(especie_id: str) -> EspecieCandidata | None:
    for entrada in _CATALOGO:
        if entrada["id"] == especie_id:
            return _a_candidata(entrada)
    return None


def construir_respuesta(especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
    """Arma la respuesta completa para una especie ya identificada.

    Incluye los registros de presencia, que es lo que alimenta las dos vistas
    de RR_18: el mapa los dibuja y la lista los tabula.
    """
    entrada = next((e for e in _CATALOGO if e["id"] == especie_id), None)
    if entrada is None:
        return None

    registros = _registros(entrada)

    return RespuestaConsulta(
        especie=_a_candidata(entrada),
        texto=entrada["texto"],
        elevacion=entrada["elevacion"],
        registros=registros,
        total_registros=len(registros),
        fuentes=list(_FUENTES),
    )


def obtener_ficha(especie: str) -> FichaEspecie | None:
    """RR_20 — ficha completa de una especie del catálogo.

    Acepta el id ('guarianthe-skinneri') o el nombre científico
    ('Guarianthe skinneri'), para que los enlaces viejos a la ficha, que usaban
    el nombre científico, sigan funcionando. None si no está en el catálogo.
    """
    buscado = _normalizar(especie.strip())
    entrada = next(
        (
            e
            for e in _CATALOGO
            if e["id"] == buscado or _normalizar(e["nombre_cientifico"]) == buscado
        ),
        None,
    )
    if entrada is None:
        return None

    registros = _registros(entrada)
    return FichaEspecie(
        id=entrada["id"],
        nombre_comun=entrada["nombre_comun"],
        nombre_cientifico=entrada["nombre_cientifico"],
        familia=entrada["familia"],
        habitat=entrada.get("habitat"),
        elevacion=entrada.get("elevacion"),
        descripcion=entrada["texto"],
        registros=registros,
        total_registros=len(registros),
        fuentes=list(_FUENTES),
    )
