"""Catálogo de especies: de dónde salen las especies y sus respuestas.

RR_17 (selección de especie ante múltiples coincidencias) y RR_18 (alternancia
entre mapa y lista de registros) necesitan datos para que su LÓGICA exista y
se pueda probar.

El resto del sistema —servicios, routers, esquemas, frontend— depende solo de
la interfaz `FuenteCatalogo` de abajo, nunca de una implementación concreta.
Los routers la reciben con `Depends(obtener_catalogo)`, que elige según
CATALOGO en el .env:

- `CatalogoDemo` (CATALOGO=demo): datos de ejemplo en memoria, sin CR-BioLM.
- `CatalogoCRBioLM` (CATALOGO=crbiolm): datos reales por MCP
  (services/catalogo_crbiolm.py).

En las pruebas se puede reemplazar con `app.dependency_overrides[obtener_catalogo]`.

Los datos de `CatalogoDemo` son ilustrativos y sirven para probar los tres
caminos de una consulta: coincidencia única, coincidencia múltiple y sin
coincidencias. No deben citarse como información científica.
"""

from __future__ import annotations

from typing import Protocol

from .. import config
from ..sanitizacion import normalizar
from ..schemas.consulta import EspecieCandidata, FichaEspecie, RegistroPresencia, RespuestaConsulta
from .catalogo_crbiolm import CatalogoCRBioLM


class FuenteCatalogo(Protocol):
    """Lo que el sistema necesita de cualquier catálogo de especies."""

    def buscar_especies(self, texto: str) -> list[EspecieCandidata]:
        """Especies que la consulta podría estar mencionando.

        Cero resultados: no se reconoció ninguna especie. Más de uno: la
        consulta es ambigua y hay que preguntarle al usuario (RR_17).
        """
        ...

    def obtener_especie(self, especie_id: str) -> EspecieCandidata | None:
        """La especie con ese id, o None si no está en el catálogo."""
        ...

    def construir_respuesta(self, especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
        """Respuesta completa para una especie ya identificada (RR_18)."""
        ...

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """Ficha completa de una especie (RR_20)."""
        ...

    def obtener_mapa(self, especie_id: str) -> bytes | None:
        """PNG del mapa de distribución, o None si no hay mapa para la especie."""
        ...


# --- implementación de demostración ------------------------------------------
# Datos provisionales. Hay pares con el mismo nombre común (guaria, cedro) para
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
    # RR_06 criterio 5 — especie SIN registros de presencia georreferenciados.
    # Sirve para probar que la respuesta se muestra sin el panel del mapa
    # cuando no hay datos geoespaciales.
    {
        "id": "hylocereus-costaricensis",
        "nombre_comun": "Pitahaya",
        "nombre_cientifico": "Hylocereus costaricensis",
        "familia": "Cactaceae",
        "alias": ["pitahaya", "pitaya", "hylocereus costaricensis"],
        "habitat": "Bosque seco del Pacífico norte; trepadora sobre árboles y cercas.",
        "elevacion": "0 – 500 msnm",
        "texto": (
            "Hylocereus costaricensis es un cactus trepador de flores blancas "
            "nocturnas y fruto rojo. Se asocia al bosque seco del Pacífico "
            "norte, pero por ahora no hay registros de presencia "
            "georreferenciados disponibles, por lo que no se puede mostrar un "
            "mapa de distribución."
        ),
        "registros": [],
    },
]

_FUENTES = ["GBIF", "Manual de Plantas de CR"]


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


class CatalogoDemo:
    """Catálogo en memoria con los datos de demostración de arriba."""

    def buscar_especies(self, texto: str) -> list[EspecieCandidata]:
        """Devuelve las especies que la consulta podría estar mencionando.

        Cero resultados significa que no se reconoció ninguna especie; más de uno
        significa que la consulta es ambigua y hay que preguntarle al usuario
        (RR_17).
        """
        consulta = normalizar(texto)
        encontradas: list[EspecieCandidata] = []

        for entrada in _CATALOGO:
            if any(normalizar(alias) in consulta for alias in entrada["alias"]):
                encontradas.append(_a_candidata(entrada))

        return encontradas

    def obtener_especie(self, especie_id: str) -> EspecieCandidata | None:
        for entrada in _CATALOGO:
            if entrada["id"] == especie_id:
                return _a_candidata(entrada)
        return None

    def construir_respuesta(self, especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
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

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """RR_20 — ficha completa de una especie del catálogo.

        Acepta el id ('guarianthe-skinneri') o el nombre científico
        ('Guarianthe skinneri'), para que los enlaces viejos a la ficha, que usaban
        el nombre científico, sigan funcionando. None si no está en el catálogo.
        """
        buscado = normalizar(especie.strip())
        entrada = next(
            (
                e
                for e in _CATALOGO
                if e["id"] == buscado or normalizar(e["nombre_cientifico"]) == buscado
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

    def obtener_mapa(self, especie_id: str) -> bytes | None:
        """Los datos de demostración no tienen mapas: solo CR-BioLM los genera."""
        return None


_CATALOGOS: dict[str, FuenteCatalogo] = {
    "demo": CatalogoDemo(),
    "crbiolm": CatalogoCRBioLM(),
}


def obtener_catalogo() -> FuenteCatalogo:
    """Dependencia de FastAPI: el catálogo que elige CATALOGO en el .env."""
    return _CATALOGOS[config.CATALOGO]
