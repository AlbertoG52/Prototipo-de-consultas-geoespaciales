"""Errores de la lógica de negocio (services/).

Los servicios no saben de HTTP: cuando una regla no se cumple lanzan uno de
estos errores, y el router lo traduce a la respuesta HTTP con
`routers.errores.errores_http()`. Así la misma lógica se puede llamar desde un
script o una prueba sin pasar por FastAPI.

Cada error trae el código HTTP que le corresponde y un `detalle` en español,
que es el texto que ve la persona.
"""


class ErrorDominio(Exception):
    """Base de los errores de negocio."""

    estado_http = 400

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


class SolicitudInvalida(ErrorDominio):
    estado_http = 400


class CredencialesInvalidas(ErrorDominio):
    estado_http = 401


class AccesoDenegado(ErrorDominio):
    estado_http = 403


class NoEncontrado(ErrorDominio):
    estado_http = 404


class Conflicto(ErrorDominio):
    estado_http = 409


class CuentaBloqueada(ErrorDominio):
    estado_http = 423


class LimiteAlcanzado(ErrorDominio):
    estado_http = 429
