"""Errores de la lógica de negocio (services/).

Los servicios no conocen HTTP: lanzan estos errores y el router los traduce con
`routers.errores.errores_http()`. Cada error trae su código HTTP y un `detalle` en español
para el usuario.
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


class TiempoAgotado(ErrorDominio):
    """La consulta superó el tiempo máximo de procesamiento."""

    estado_http = 504

    def __init__(self, segundos: float):
        unidad = "segundo" if segundos == 1 else "segundos"
        super().__init__(
            f"La consulta superó el tiempo máximo de {segundos:g} {unidad} y se canceló. "
            "No se descontó de tus consultas del día: puedes reintentarla."
        )
        self.segundos = segundos
