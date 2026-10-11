"""Base de los esquemas que el backend DEVUELVE (respuestas de la API)."""

from pydantic import BaseModel, ConfigDict


class EsquemaSalida(BaseModel):
    """Esquema de respuesta.

    Un campo con valor por defecto (p. ej. `candidatos: list = []`) siempre
    viene en la respuesta. Esta opción lo marca como obligatorio en el contrato
    OpenAPI, así los tipos que genera el frontend (`npm run tipos`) no lo ven
    como opcional y no obligan a comprobar `undefined` en cada uso.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
