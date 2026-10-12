"""Adaptador MCP: la única puerta del backend hacia CR-BioLM.

CR-BioLM expone sus servicios (catálogo del Manual de Plantas, ocurrencias de
GBIF, mapas y respuestas en lenguaje natural) como herramientas de un servidor
MCP. Este módulo es lo único del backend que sabe que ese servidor existe: abre
la conexión, llama una herramienta y devuelve el resultado ya interpretado como
un `Sobre`. Ningún router ni otro servicio importa el SDK de MCP.

Uso, desde código síncrono (los endpoints del proyecto lo son):

    from app.services import mcp_cliente

    sobre = mcp_cliente.llamar("get_species", name="Quercus costaricensis")
    sobre.valor["elev_min"], sobre.cita, sobre.advertencia

Desde una función `async` se usa `allamar(...)` con `await`.

Qué hace:
- Abre una sesión por llamada. Es lo más simple y suficiente para el
  prototipo: el servidor corre en la misma máquina o en la red de Docker.
- Corta la llamada si pasa de MCP_TIMEOUT_SEGUNDOS, o antes si la consulta que
  la hizo tiene menos tiempo restante (RR_38, ver tiempo.plazo).
- Reintenta solo cuando no se pudo conectar, y solo si la herramienta todavía no
  se había pedido. Una llamada que ya llegó al servidor no se repite: podría
  haber gastado una consulta al LLM (L2), y repetirla la cobraría dos veces.
- Convierte cada fallo en una excepción propia (ver `ErrorMCP`), para que los
  routers muestren un mensaje claro con opción de reintentar (RR_05) sin
  conocer los detalles del protocolo.
- Registra en el log cuánto tardó cada llamada (el tiempo de la consulta
  completa lo registra RR_57, ver services/tiempos.py).

Qué NO hace, a propósito:
- No decide qué herramientas llamar: eso es del flujo de consultas.
- No aplica límites ni costos por rol (RR_62, RR_77): eso va por encima.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from typing import Any

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, TextContent

from .. import config
from ..tiempo import alcanza_para_esperar, segundos_restantes

# El logger de uvicorn es el que ya aparece en los logs del contenedor.
logger = logging.getLogger("uvicorn.error")

# Valores de 'confidence' que usa CR-BioLM en su sobre de procedencia.
CONFIANZA_EXACTA = "exact"
CONFIANZA_ESTIMADA = "estimated"
CONFIANZA_INSUFICIENTE = "insufficient"
CONFIANZAS = (CONFIANZA_EXACTA, CONFIANZA_ESTIMADA, CONFIANZA_INSUFICIENTE)

# Fallos de red en los que la petición no llegó a procesarse: vale la pena
# reintentar si la herramienta todavía no se había pedido.
_FALLOS_DE_CONEXION = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError)


# --- errores ------------------------------------------------------------------


class ErrorMCP(Exception):
    """Cualquier fallo al usar CR-BioLM. Los routers lo traducen a RR_05.

    El mensaje es para el log, no para el usuario: puede traer detalles
    internos (URL, nombre de la herramienta, error del servidor).
    """

    def __init__(self, herramienta: str, detalle: str):
        super().__init__(f"{herramienta}: {detalle}")
        self.herramienta = herramienta
        self.detalle = detalle


class MCPNoDisponible(ErrorMCP):
    """No se pudo hablar con el servidor: está apagado, la URL está mal o rechazó
    la conexión. Reintentar más tarde puede funcionar."""


class MCPTiempoAgotado(ErrorMCP):
    """La llamada superó MCP_TIMEOUT_SEGUNDOS o el tiempo que le quedaba a la consulta (RR_38)."""


class MCPErrorHerramienta(ErrorMCP):
    """El servidor respondió, pero la herramienta falló o no existe."""


class MCPRespuestaInvalida(ErrorMCP):
    """La herramienta respondió algo que no es el sobre de procedencia esperado."""


# --- resultado ----------------------------------------------------------------


@dataclass(frozen=True)
class Sobre:
    """El sobre de procedencia que devuelve cada herramienta de CR-BioLM.

    Traduce a los nombres del proyecto los campos de CR-BioLM:
    value -> valor, source -> fuente, citation -> cita,
    confidence -> confianza, caveat -> advertencia.

    - fuente: MPCR, GBIF, DEM, SINAC o combinaciones como "MPCR+GBIF".
    - cita: referencia lista para mostrar, p. ej. "Tomo IV, p. 320" (RR_50, RR_51).
    - confianza: "exact", "estimated" o "insufficient".
    - advertencia: si no está vacía, hay que mostrarla junto al dato; no se descarta.
    """

    valor: Any
    fuente: str
    cita: str = ""
    confianza: str = CONFIANZA_EXACTA
    advertencia: str = ""

    @property
    def es_suficiente(self) -> bool:
        """False cuando CR-BioLM avisa que no hay datos suficientes (RR_53)."""
        return self.confianza != CONFIANZA_INSUFICIENTE

    @classmethod
    def desde_dict(cls, datos: Any, herramienta: str) -> Sobre:
        if not isinstance(datos, dict) or "value" not in datos or "source" not in datos:
            raise MCPRespuestaInvalida(herramienta, "la respuesta no trae 'value' y 'source'")
        confianza = datos.get("confidence") or CONFIANZA_EXACTA
        if confianza not in CONFIANZAS:
            raise MCPRespuestaInvalida(herramienta, f"confianza desconocida: {confianza!r}")
        return cls(
            valor=datos["value"],
            fuente=str(datos["source"]),
            cita=str(datos.get("citation") or ""),
            confianza=confianza,
            advertencia=str(datos.get("caveat") or ""),
        )


# --- llamadas -----------------------------------------------------------------


def llamar(herramienta: str, **argumentos: Any) -> Sobre:
    """Llama una herramienta de CR-BioLM y devuelve su sobre.

    Para código síncrono. Dentro de una función `async` use `allamar`, porque
    esta función abre su propio ciclo de eventos.

    Los argumentos en None se omiten: en CR-BioLM, omitir un filtro es la forma
    de no aplicarlo.
    """
    return anyio.run(partial(allamar, herramienta, **argumentos))


async def allamar(herramienta: str, **argumentos: Any) -> Sobre:
    """Versión asíncrona de `llamar`."""
    argumentos = {clave: valor for clave, valor in argumentos.items() if valor is not None}
    inicio = time.perf_counter()
    try:
        resultado = await _con_reintentos(herramienta, _llamar_herramienta, herramienta, argumentos)
        sobre = _a_sobre(herramienta, resultado)
    except ErrorMCP as exc:
        logger.warning("MCP %s falló en %d ms: %s", herramienta, _ms_desde(inicio), exc)
        raise
    logger.info("MCP %s respondió en %d ms", herramienta, _ms_desde(inicio))
    return sobre


def herramientas_disponibles() -> list[str]:
    """Nombres de las herramientas que ofrece el servidor. Sirve para comprobar
    que la conexión funciona (GET /mcp-check)."""
    try:
        return anyio.run(_con_reintentos, "list_tools", _listar_herramientas)
    except ErrorMCP as exc:
        logger.warning("MCP: no se pudieron listar las herramientas: %s", exc)
        raise


# --- detalles internos --------------------------------------------------------


class _Progreso:
    """Recuerda si la herramienta ya se pidió, para no reintentar en ese caso."""

    def __init__(self) -> None:
        self.pedida = False


async def _llamar_herramienta(
    progreso: _Progreso, herramienta: str, argumentos: dict
) -> CallToolResult:
    async with _sesion() as sesion:
        progreso.pedida = True
        return await sesion.call_tool(herramienta, argumentos)


async def _listar_herramientas(progreso: _Progreso) -> list[str]:
    async with _sesion() as sesion:
        progreso.pedida = True
        respuesta = await sesion.list_tools()
        return [herramienta.name for herramienta in respuesta.tools]


@asynccontextmanager
async def _sesion() -> AsyncIterator[ClientSession]:
    """Conexión HTTP + sesión MCP ya inicializada."""
    transporte = streamablehttp_client(
        config.MCP_URL,
        timeout=config.MCP_TIMEOUT_SEGUNDOS,
        sse_read_timeout=config.MCP_TIMEOUT_SEGUNDOS,
    )
    async with transporte as (lectura, escritura, _), ClientSession(lectura, escritura) as sesion:
        await sesion.initialize()
        yield sesion


async def _con_reintentos(herramienta: str, operacion, *argumentos):
    """Ejecuta `operacion` con tiempo máximo y reintentos de conexión.

    Se reintenta solo si no se pudo conectar Y la herramienta todavía no se
    había pedido. Entre intentos se espera MCP_ESPERA_REINTENTO_SEGUNDOS, salvo
    que a la consulta ya no le alcance el tiempo para otro intento (RR_38).
    """
    intentos = config.MCP_REINTENTOS_CONEXION + 1
    for intento in range(1, intentos + 1):
        limite = _tiempo_para_la_llamada(herramienta)
        progreso = _Progreso()
        try:
            with anyio.fail_after(limite):
                return await operacion(progreso, *argumentos)
        except Exception as exc:
            error, reintentable = _clasificar(herramienta, exc, limite)
            if (
                reintentable
                and not progreso.pedida
                and intento < intentos
                and alcanza_para_esperar(config.MCP_ESPERA_REINTENTO_SEGUNDOS)
            ):
                logger.warning(
                    "MCP %s: no se pudo conectar (intento %d de %d), se reintenta",
                    herramienta,
                    intento,
                    intentos,
                )
                await anyio.sleep(config.MCP_ESPERA_REINTENTO_SEGUNDOS)
                continue
            raise error from exc
    raise AssertionError("inalcanzable")  # el ciclo siempre retorna o lanza


def _tiempo_para_la_llamada(herramienta: str) -> float:
    """MCP_TIMEOUT_SEGUNDOS, o lo que le quede a la consulta si es menos (RR_38)."""
    restantes = segundos_restantes()
    if restantes is None:
        return config.MCP_TIMEOUT_SEGUNDOS
    if restantes <= 0:
        raise MCPTiempoAgotado(herramienta, "la consulta ya había agotado su tiempo máximo")
    return min(config.MCP_TIMEOUT_SEGUNDOS, restantes)


def _clasificar(herramienta: str, exc: Exception, limite: float) -> tuple[ErrorMCP, bool]:
    """Traduce un fallo del SDK o de la red a un ErrorMCP del proyecto.

    El booleano dice si vale la pena reintentar: solo cuando no se pudo conectar.
    """
    if _contiene(exc, TimeoutError):
        detalle = f"superó {limite:g} s sin responder"
        return MCPTiempoAgotado(herramienta, detalle), False

    rechazo = _contiene(exc, httpx.HTTPStatusError)
    if rechazo is not None:
        detalle = (
            f"el servidor respondió HTTP {rechazo.response.status_code}; "
            f"revise MCP_URL ({config.MCP_URL})"
        )
        return MCPNoDisponible(herramienta, detalle), False

    caida = _contiene(exc, *_FALLOS_DE_CONEXION)
    if caida is not None:
        detalle = f"no se pudo conectar con {config.MCP_URL}: {caida!r}"
        return MCPNoDisponible(herramienta, detalle), True

    protocolo = _contiene(exc, McpError)
    if protocolo is not None:
        # p. ej. "Session terminated": la ruta no es la de un servidor MCP.
        detalle = (
            f"el servidor rechazó la sesión MCP ({protocolo}); revise MCP_URL ({config.MCP_URL})"
        )
        return MCPNoDisponible(herramienta, detalle), False

    return ErrorMCP(herramienta, f"error inesperado: {exc!r}"), False


def _contiene[E: BaseException](exc: BaseException, *tipos: type[E]) -> E | None:
    """Busca un error de los tipos dados dentro de `exc`.

    El SDK de MCP trabaja con grupos de tareas, así que un fallo de red suele
    llegar envuelto en un ExceptionGroup, a veces anidado, o como causa de otro.
    """
    if isinstance(exc, tipos):
        return exc
    internas = list(exc.exceptions) if isinstance(exc, BaseExceptionGroup) else []
    if exc.__cause__ is not None:
        internas.append(exc.__cause__)
    for interna in internas:
        encontrada = _contiene(interna, *tipos)
        if encontrada is not None:
            return encontrada
    return None


def _a_sobre(herramienta: str, resultado: CallToolResult) -> Sobre:
    """Interpreta la respuesta de una herramienta como su sobre de procedencia."""
    texto = next(
        (bloque.text for bloque in resultado.content if isinstance(bloque, TextContent)), ""
    )
    if resultado.isError:
        raise MCPErrorHerramienta(herramienta, texto or "la herramienta reportó un error")

    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        datos = None
    if not (isinstance(datos, dict) and "value" in datos) and isinstance(
        resultado.structuredContent, dict
    ):
        datos = resultado.structuredContent
    if datos is None:
        raise MCPRespuestaInvalida(herramienta, "la respuesta no es JSON")
    return Sobre.desde_dict(datos, herramienta)


def _ms_desde(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)
