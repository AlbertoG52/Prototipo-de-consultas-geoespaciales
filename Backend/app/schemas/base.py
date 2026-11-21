"""Base de los esquemas de respuesta de la API."""

from pydantic import BaseModel, ConfigDict


class EsquemaSalida(BaseModel):
    """Esquema de respuesta.

    Marca como obligatorios en OpenAPI los campos con valor por defecto, que siempre vienen
    en la respuesta. Así los tipos del frontend (`npm run tipos`) no los ven como
    opcionales.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
