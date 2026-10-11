"""Pruebas del adaptador MCP (services/mcp_cliente.py).

No necesitan base de datos ni CR-BioLM: levantan un servidor MCP falso, en este
mismo proceso, con herramientas que imitan las respuestas de CR-BioLM (el sobre
de procedencia) y sus fallos. Se ejecutan con:
    docker compose exec backend python -m pytest tests/test_mcp_cliente.py -q
"""

import socket
import threading
import time

import anyio
import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app import config
from app.services import mcp_cliente
from app.services.mcp_cliente import (
    MCPErrorHerramienta,
    MCPNoDisponible,
    MCPRespuestaInvalida,
    MCPTiempoAgotado,
    Sobre,
)

# --- servidor falso -------------------------------------------------------------

falso = FastMCP("crbiolm-falso")


@falso.tool()
def get_species(name: str) -> dict:
    """Imita la ficha de una especie de CR-BioLM."""
    return {
        "value": {"species": name, "elev_min": 2200, "elev_max": 3300},
        "source": "MPCR",
        "citation": "Manual de Plantas de Costa Rica, Tomo IV, p. 320",
        "confidence": "exact",
        "caveat": "",
    }


@falso.tool()
def search_species(habit: str | None = None, elev_lo: int | None = None) -> dict:
    """Devuelve los filtros que recibió, para comprobar cuáles llegaron."""
    return {"value": {"habit": habit, "elev_lo": elev_lo}, "source": "MPCR"}


@falso.tool()
def get_occurrences(species: str) -> dict:
    """Imita una especie sin registros en GBIF."""
    return {
        "value": {"n": 0},
        "source": "GBIF",
        "confidence": "insufficient",
        "caveat": f"No GBIF occurrences found for '{species}' in Costa Rica.",
    }


@falso.tool()
def herramienta_que_falla() -> dict:
    raise ValueError("detalle interno que no debe llegar al usuario")


@falso.tool()
def sin_sobre() -> str:
    return "texto suelto, sin sobre de procedencia"


@falso.tool()
def confianza_rara() -> dict:
    return {"value": 1, "source": "MPCR", "confidence": "quizas"}


@falso.tool()
async def lenta() -> dict:
    # async: un time.sleep bloquearía el servidor falso para las pruebas siguientes.
    await anyio.sleep(3)
    return {"value": None, "source": "MPCR"}


async def _ruta_rota(_peticion):
    return PlainTextResponse("error interno", status_code=500)


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def url_falsa():
    puerto = _puerto_libre()
    aplicacion = falso.streamable_http_app()
    aplicacion.router.routes.append(Route("/roto", _ruta_rota, methods=["GET", "POST", "DELETE"]))
    servidor = uvicorn.Server(
        uvicorn.Config(
            aplicacion,
            host="127.0.0.1",
            port=puerto,
            log_config=None,
            log_level="warning",
        )
    )
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + 10
    while not servidor.started:
        assert time.monotonic() < limite, "el servidor MCP falso no arrancó"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{puerto}/mcp"
    servidor.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture
def conectado(monkeypatch, url_falsa):
    """El adaptador apuntando al servidor falso, con tiempos cortos."""
    monkeypatch.setattr(config, "MCP_URL", url_falsa)
    monkeypatch.setattr(config, "MCP_TIMEOUT_SEGUNDOS", 1.0)
    monkeypatch.setattr(config, "MCP_REINTENTOS_CONEXION", 2)
    monkeypatch.setattr(config, "MCP_ESPERA_REINTENTO_SEGUNDOS", 0)


# --- llamadas correctas ---------------------------------------------------------


def test_devuelve_el_sobre_con_los_nombres_del_proyecto(conectado):
    sobre = mcp_cliente.llamar("get_species", name="Quercus costaricensis")

    assert sobre == Sobre(
        valor={"species": "Quercus costaricensis", "elev_min": 2200, "elev_max": 3300},
        fuente="MPCR",
        cita="Manual de Plantas de Costa Rica, Tomo IV, p. 320",
        confianza="exact",
        advertencia="",
    )
    assert sobre.es_suficiente


def test_los_argumentos_en_none_no_se_envian(conectado):
    sobre = mcp_cliente.llamar("search_species", habit="arbusto", elev_lo=None)

    assert sobre.valor == {"habit": "arbusto", "elev_lo": None}


def test_datos_insuficientes_llegan_como_sobre_con_advertencia(conectado):
    """RR_53: no es un error, es un resultado que hay que mostrar con su aviso."""
    sobre = mcp_cliente.llamar("get_occurrences", species="Especie inventada")

    assert not sobre.es_suficiente
    assert sobre.fuente == "GBIF"
    assert "No GBIF occurrences" in sobre.advertencia


def test_lista_las_herramientas_del_servidor(conectado):
    herramientas = mcp_cliente.herramientas_disponibles()

    assert {"get_species", "search_species", "get_occurrences"} <= set(herramientas)


# --- fallos ---------------------------------------------------------------------


def test_herramienta_que_falla(conectado):
    with pytest.raises(MCPErrorHerramienta) as error:
        mcp_cliente.llamar("herramienta_que_falla")
    assert error.value.herramienta == "herramienta_que_falla"


def test_herramienta_inexistente(conectado):
    with pytest.raises(MCPErrorHerramienta):
        mcp_cliente.llamar("no_existe")


@pytest.mark.parametrize("herramienta", ["sin_sobre", "confianza_rara"])
def test_respuesta_sin_sobre_valido(conectado, herramienta):
    with pytest.raises(MCPRespuestaInvalida):
        mcp_cliente.llamar(herramienta)


def test_tiempo_agotado(conectado, monkeypatch):
    """Base de RR_38: la llamada se corta al pasar el tiempo máximo."""
    monkeypatch.setattr(config, "MCP_TIMEOUT_SEGUNDOS", 0.5)
    inicio = time.monotonic()

    with pytest.raises(MCPTiempoAgotado):
        mcp_cliente.llamar("lenta")
    assert time.monotonic() - inicio < 2.5


def test_servidor_apagado_reintenta_y_avisa(monkeypatch, caplog):
    monkeypatch.setattr(config, "MCP_URL", f"http://127.0.0.1:{_puerto_libre()}/mcp")
    monkeypatch.setattr(config, "MCP_REINTENTOS_CONEXION", 2)
    monkeypatch.setattr(config, "MCP_ESPERA_REINTENTO_SEGUNDOS", 0)
    caplog.set_level("WARNING", logger="uvicorn.error")

    with pytest.raises(MCPNoDisponible):
        mcp_cliente.llamar("get_species", name="Quercus costaricensis")
    reintentos = [r for r in caplog.records if "se reintenta" in r.getMessage()]
    assert len(reintentos) == 2


@pytest.mark.parametrize("ruta", ["/otra-ruta", "/roto"])
def test_url_equivocada_no_se_reintenta(conectado, monkeypatch, caplog, ruta):
    """Si el servidor responde con un error HTTP (ruta inexistente o fallo del
    servidor web), es un problema de configuración: reintentar no lo arregla, y
    se avisa de inmediato en lugar de esperar al tiempo máximo."""
    monkeypatch.setattr(config, "MCP_URL", config.MCP_URL.replace("/mcp", ruta))
    caplog.set_level("WARNING", logger="uvicorn.error")
    inicio = time.monotonic()

    with pytest.raises(MCPNoDisponible) as error:
        mcp_cliente.llamar("get_species", name="Quercus costaricensis")
    assert "MCP_URL" in error.value.detalle
    assert time.monotonic() - inicio < 0.9
    assert not [r for r in caplog.records if "se reintenta" in r.getMessage()]


# --- GET /mcp-check -------------------------------------------------------------


def test_mcp_check_lista_las_herramientas(conectado):
    from fastapi.testclient import TestClient

    from app.main import app

    respuesta = TestClient(app).get("/mcp-check")

    assert respuesta.status_code == 200
    assert "get_species" in respuesta.json()["herramientas"]


def test_mcp_check_sin_servidor_responde_503_sin_detalles_internos(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    url = f"http://127.0.0.1:{_puerto_libre()}/mcp"
    monkeypatch.setattr(config, "MCP_URL", url)
    monkeypatch.setattr(config, "MCP_REINTENTOS_CONEXION", 0)

    respuesta = TestClient(app).get("/mcp-check")

    assert respuesta.status_code == 503
    assert url not in respuesta.text
