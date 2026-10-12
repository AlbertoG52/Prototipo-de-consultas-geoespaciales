"""Lógica de una consulta al agente — RR_02, RR_09, RR_17, RR_18.

El router (routers/consultas.py) solo recibe la petición y llama a
`procesar_consulta`; las reglas viven aquí:

- Ninguna especie reconocida  -> estado "sin_coincidencias".
- Varias especies reconocidas -> estado "ambigua" y la lista de candidatas
  (RR_17). El usuario elige una y el frontend reenvía la consulta con
  'especie_id' (y 'consulta_id' si es una cuenta registrada).
- Una sola especie            -> estado "resuelta" con la respuesta completa.

Solo el camino resuelto consume una consulta del límite diario: pedirle al
usuario que desambigüe, o avisarle que no se encontró nada, no le cuesta.

De un usuario registrado se guardan los tres estados dentro de una
conversación (RR_09), para poder reabrirla completa. Del visitante no se
guarda nada (RR_00_11).

RR_38 — cada consulta tiene SEGUNDOS_MAXIMOS_CONSULTA (config.py) para
completarse. Si se pasa, se cancela con `TiempoAgotado` (HTTP 504) ANTES de
guardar o cobrar nada, así que reintentarla no le cuesta al usuario.

RR_57 — el tiempo de cada consulta, termine bien o mal, queda registrado
(services/tiempos.py) para que el equipo técnico encuentre las lentas.
"""

import logging

from sqlalchemy.orm import Session

from .. import config
from ..dominio import EstadoConsulta
from ..errores import Conflicto, LimiteAlcanzado, NoEncontrado, SolicitudInvalida, TiempoAgotado
from ..models import Consulta, Conversacion
from ..schemas.consulta import ConsultaOut, ConsultaRequest, EspecieCandidata, RespuestaConsulta
from ..security import Identidad
from ..tiempo import ahora, plazo, verificar_plazo
from .catalogo import FuenteCatalogo
from .mcp_cliente import MCPTiempoAgotado
from .tiempos import medir_consulta
from .uso import consultas_hoy, limite_de, registrar_consumo_anonimo

logger = logging.getLogger("uvicorn.error")

# Largo máximo del título de una conversación (columna de la tabla 012).
LARGO_TITULO = 120

MENSAJE_SIN_COINCIDENCIAS = (
    "No se reconoció ninguna especie en la consulta. "
    "Intenta con el nombre común o científico de una planta."
)
MENSAJE_AMBIGUA = "La consulta coincide con más de una especie. Selecciona cuál te interesa."

_MENSAJES = {
    EstadoConsulta.SIN_COINCIDENCIAS: MENSAJE_SIN_COINCIDENCIAS,
    EstadoConsulta.AMBIGUA: MENSAJE_AMBIGUA,
}


def procesar_consulta(
    db: Session,
    identidad: Identidad,
    datos: ConsultaRequest,
    catalogo: FuenteCatalogo,
) -> ConsultaOut:
    """Procesa una consulta en lenguaje natural (ver el docstring del módulo).

    RR_38: todo el procesamiento corre dentro del tiempo máximo de la consulta.
    RR_57: y se mide, incluido el caso en que se corta o falla.
    """
    segundos = config.SEGUNDOS_MAXIMOS_CONSULTA
    with medir_consulta(identidad) as medicion:
        try:
            with plazo(segundos):
                salida = _procesar(db, identidad, datos, catalogo)
        except (TiempoAgotado, MCPTiempoAgotado) as error:
            # Para el equipo técnico: qué consulta se cortó y en qué paso.
            logger.warning("Consulta cancelada por superar %g s: %s", segundos, error)
            raise TiempoAgotado(segundos) from error
        medicion.terminar(salida)
        return salida


def _procesar(
    db: Session,
    identidad: Identidad,
    datos: ConsultaRequest,
    catalogo: FuenteCatalogo,
) -> ConsultaOut:
    limite = limite_de(identidad)
    usadas = consultas_hoy(db, identidad)

    # RR_17 con cuenta: elegir la especie de una consulta ambigua ya guardada.
    if datos.consulta_id is not None:
        return _resolver_pendiente(db, identidad, datos, catalogo, limite, usadas)

    if usadas >= limite:
        raise _limite_alcanzado(identidad)

    candidatas = _identificar_especies(datos, catalogo)
    if not candidatas:
        estado, respuesta = EstadoConsulta.SIN_COINCIDENCIAS, None
    elif len(candidatas) > 1:
        # RR_17 criterios 1 y 2: presentar las coincidencias para que elija.
        estado, respuesta = EstadoConsulta.AMBIGUA, None
    else:
        estado = EstadoConsulta.RESUELTA
        respuesta = _construir_respuesta(catalogo, candidatas[0].id, datos.texto)

    # RR_38: si el tiempo se acabó mientras se buscaba, se corta aquí, antes de
    # guardar o cobrar nada.
    verificar_plazo()

    resuelta = estado == EstadoConsulta.RESUELTA
    mensaje = _MENSAJES.get(estado)
    ofrecidas = candidatas if estado == EstadoConsulta.AMBIGUA else []
    restantes = max(limite - usadas - (1 if resuelta else 0), 0)

    # --- visitante: se cuenta, pero no se guarda (RR_00_11) -----------------
    if identidad.usuario is None:
        if resuelta and identidad.anon_id is not None:
            registrar_consumo_anonimo(db, identidad.anon_id)
        return ConsultaOut(
            estado=estado,
            texto=datos.texto,
            respuesta=respuesta,
            candidatos=ofrecidas,
            mensaje=mensaje,
            consultas_restantes=restantes,
        )

    # --- cuenta registrada: se guarda en su conversación (RR_09) ------------
    momento = ahora()
    conversacion = _conversacion_de(db, identidad.usuario.id, datos.conversacion_id, datos.texto)
    conversacion.actualizada_en = momento

    consulta = Consulta(
        usuario_id=identidad.usuario.id,
        conversacion_id=conversacion.id,
        texto=datos.texto,
        sesion_id=identidad.sesion_id,
        estado=estado,
        respuesta=respuesta.model_dump(mode="json") if respuesta else None,
        candidatos=[c.model_dump(mode="json") for c in ofrecidas] or None,
        mensaje=mensaje,
        resuelta_en=momento if resuelta else None,
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)

    return ConsultaOut(
        id=consulta.id,
        conversacion_id=conversacion.id,
        estado=estado,
        texto=consulta.texto,
        respuesta=respuesta,
        candidatos=ofrecidas,
        mensaje=mensaje,
        realizada_en=consulta.realizada_en,
        consultas_restantes=restantes,
    )


def _identificar_especies(
    datos: ConsultaRequest, catalogo: FuenteCatalogo
) -> list[EspecieCandidata]:
    """Las especies candidatas: la que eligió el usuario, o las que reconoce el texto."""
    if not datos.especie_id:
        return catalogo.buscar_especies(datos.texto)
    # El usuario ya eligió entre las candidatas (RR_17 criterio 3).
    elegida = catalogo.obtener_especie(datos.especie_id)
    if elegida is None:
        raise NoEncontrado("La especie seleccionada no está en el catálogo.")
    return [elegida]


def _resolver_pendiente(
    db: Session,
    identidad: Identidad,
    datos: ConsultaRequest,
    catalogo: FuenteCatalogo,
    limite: int,
    usadas: int,
) -> ConsultaOut:
    """Resuelve una consulta ambigua guardada con la especie que eligió el usuario.

    Se actualiza esa misma fila en lugar de crear otra: así la conversación
    muestra una sola consulta y se cobra una sola vez, aunque se elija la
    especie días después. La fila se bloquea mientras se resuelve, para que
    dos clics seguidos no la cobren dos veces.
    """
    if identidad.usuario is None:
        raise SolicitudInvalida("Solo las cuentas registradas guardan consultas pendientes.")
    if not datos.especie_id:
        raise SolicitudInvalida("Falta la especie elegida.")

    consulta = (
        db.query(Consulta)
        .filter(Consulta.id == datos.consulta_id, Consulta.usuario_id == identidad.usuario.id)
        .with_for_update()
        .first()
    )
    if consulta is None:
        raise NoEncontrado("La consulta no existe.")
    if consulta.estado != EstadoConsulta.AMBIGUA:
        raise Conflicto("Esta consulta ya se resolvió.")

    ofrecidas = {c["id"] for c in (consulta.candidatos or [])}
    if datos.especie_id not in ofrecidas:
        raise SolicitudInvalida("La especie elegida no es una de las opciones de esta consulta.")

    if usadas >= limite:
        raise _limite_alcanzado(identidad, pendiente=True)

    respuesta = _construir_respuesta(catalogo, datos.especie_id, consulta.texto)
    verificar_plazo()  # RR_38: antes de resolverla y cobrarla
    momento = ahora()

    consulta.estado = EstadoConsulta.RESUELTA
    consulta.respuesta = respuesta.model_dump(mode="json")
    consulta.resuelta_en = momento
    consulta.conversacion.actualizada_en = momento
    db.commit()
    db.refresh(consulta)

    return ConsultaOut(
        id=consulta.id,
        conversacion_id=consulta.conversacion_id,
        estado=EstadoConsulta.RESUELTA,
        texto=consulta.texto,
        respuesta=respuesta,
        realizada_en=consulta.realizada_en,
        consultas_restantes=max(limite - usadas - 1, 0),
    )


def _limite_alcanzado(identidad: Identidad, pendiente: bool = False) -> LimiteAlcanzado:
    if identidad.es_anonimo:
        return LimiteAlcanzado(
            "Alcanzaste el límite de consultas disponibles sin cuenta. "
            "Crea una cuenta para obtener más consultas diarias."
        )
    if pendiente:
        return LimiteAlcanzado(
            "Alcanzaste tu límite de consultas por hoy. La consulta queda pendiente: "
            "podrás elegir la especie cuando se restablezca tu límite."
        )
    return LimiteAlcanzado("Alcanzaste tu límite de consultas por hoy.")


def _construir_respuesta(
    catalogo: FuenteCatalogo, especie_id: str, texto: str
) -> RespuestaConsulta:
    respuesta = catalogo.construir_respuesta(especie_id, texto)
    if respuesta is None:
        raise NoEncontrado("No hay información disponible para esa especie.")
    return respuesta


def _conversacion_de(
    db: Session, usuario_id: int, conversacion_id: int | None, texto: str
) -> Conversacion:
    """La conversación donde se guarda la consulta; si no viene, se crea una.

    Solo se acepta una conversación del mismo usuario: con el id de otra
    persona se responde 404, igual que si no existiera.
    """
    if conversacion_id is None:
        conversacion = Conversacion(usuario_id=usuario_id, titulo=texto[:LARGO_TITULO])
        db.add(conversacion)
        db.flush()  # para tener el id antes de guardar la consulta
        return conversacion

    existente = (
        db.query(Conversacion)
        .filter(Conversacion.id == conversacion_id, Conversacion.usuario_id == usuario_id)
        .first()
    )
    if existente is None:
        raise NoEncontrado("La conversación no existe.")
    return existente
