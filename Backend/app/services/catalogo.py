"""Catálogo de especies.

El resto del sistema depende solo de la interfaz `FuenteCatalogo`. Los routers reciben el
catálogo de CR-BioLM (services/catalogo_crbiolm.py) con `Depends(obtener_catalogo)`. Las
pruebas lo reemplazan por un catálogo en memoria (tests/catalogo_demo.py).
"""

from __future__ import annotations

from typing import Protocol

from ..schemas.consulta import EspecieCandidata, FichaEspecie, RespuestaConsulta
from .catalogo_crbiolm import CatalogoCRBioLM


class FuenteCatalogo(Protocol):
    """Lo que el sistema necesita de cualquier catálogo de especies."""

    def buscar_especies(self, texto: str) -> list[EspecieCandidata]:
        """Especies que la consulta podría estar mencionando. Cero: no se reconoció ninguna.
        Más de una: la consulta es ambigua y se le pregunta al usuario.
        """
        ...

    def obtener_especie(self, especie_id: str) -> EspecieCandidata | None:
        """La especie con ese id, o None si no está en el catálogo."""
        ...

    def construir_respuesta(self, especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
        """Respuesta completa para una especie ya identificada."""
        ...

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """Ficha completa de una especie."""
        ...

    def obtener_mapa(self, especie_id: str) -> bytes | None:
        """PNG del mapa de distribución, o None si no hay mapa para la especie."""
        ...


# El catálogo que usa la aplicación. Las pruebas lo reemplazan con monkeypatch.
catalogo_activo: FuenteCatalogo = CatalogoCRBioLM()


def obtener_catalogo() -> FuenteCatalogo:
    """Dependencia de FastAPI: el catálogo de especies de CR-BioLM."""
    return catalogo_activo
