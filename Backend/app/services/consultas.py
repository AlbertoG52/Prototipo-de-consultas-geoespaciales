"""Lógica de una consulta al agente.

- No es una consulta -> "orientacion" con su motivo (saludo, ayuda, otro idioma, sin
  sentido). Se detecta antes de buscar especies, sin llamar a CR-BioLM.
- Ninguna especie -> "sin_coincidencias", u "orientacion" si nada en el texto habla de
  plantas o pregunta por la flora de otro país.
- Varias especies -> "ambigua" con las candidatas. El frontend reenvía la consulta con
  'especie_id' (y 'consulta_id' si es una cuenta).
- Un nombre común encontrado solo en parte ("cedro amargo" -> "amargo") -> "ambigua" aunque
  haya una sola candidata.
- Una sola especie -> "resuelta" con la respuesta completa.
- Un tipo de consulta que su rol no tiene -> "orientacion" con el motivo
  "tipo_no_permitido".

Solo "resuelta" cuenta para el límite. El límite se revisa antes de procesar: si se
alcanzó, no se llama a CR-BioLM y se responde 429 con el límite y cuándo se restablece.

De una cuenta se guardan todos los estados en su conversación; del visitante no se guarda
nada.

Cada consulta tiene SEGUNDOS_MAXIMOS_CONSULTA para completarse; si se pasa, se cancela
(504) antes de guardar o contar nada. Su tiempo queda registrado (services/tiempos.py). El
mapa y las fuentes se incluyen según las preferencias de quien consulta
(services/preferencias.py), antes de guardar la respuesta.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from .. import config
from ..dominio import EstadoConsulta, IntencionConsulta, MotivoOrientacion, TipoPregunta
from ..errores import (
    AccesoDenegado,
    Conflicto,
    LimiteAlcanzado,
    NoEncontrado,
    SolicitudInvalida,
    TiempoAgotado,
)
from ..models import Consulta, Conversacion
from ..schemas.consulta import ConsultaOut, ConsultaRequest, EspecieCandidata, RespuestaConsulta
from ..security import Identidad
from ..tiempo import ahora, fecha_para_mostrar, plazo, verificar_plazo
from . import permisos, preferencias
from .catalogo import FuenteCatalogo
from .intencion import analizar
from .mcp_cliente import MCPTiempoAgotado
from .permisos import Permisos
from .preprocesamiento import (
    EJEMPLOS_DE_CONSULTA,
    fuera_de_costa_rica,
    fuera_de_tema,
    interpretar,
    mensaje_de,
)
from .tiempos import medir_consulta
from .uso import (
    POR_PERIODO,
    consultas_del_periodo,
    fin_del_periodo,
    limite_de,
    periodo_de,
    registrar_consumo_anonimo,
)

logger = logging.getLogger("uvicorn.error")

# Largo máximo del título de una conversación.
LARGO_TITULO = 120

MENSAJE_SIN_COINCIDENCIAS = (
    "No se reconoció ninguna especie en la consulta. "
    "Intenta con el nombre común o científico de una planta."
)
MENSAJE_AMBIGUA = (
    "La consulta coincide con más de una especie. Elige una o escribe un nombre más específico."
)
# El nombre completo no está; solo una parte de él.
MENSAJE_NOMBRE_INCOMPLETO = "No encontré «{frase}». ¿Te refieres a alguna de estas especies?"


@dataclass
class _Resultado:
    """Qué se responde a una consulta, antes de guardarla."""

    estado: EstadoConsulta
    respuesta: RespuestaConsulta | None = None
    candidatas: list[EspecieCandidata] = field(default_factory=list)  # solo en AMBIGUA
    mensaje: str | None = None
    motivo: MotivoOrientacion | None = None  # solo en ORIENTACION
    # Tipos de consulta de quien pregunta, para no sugerirle otros.
    permitidos: frozenset[TipoPregunta] = permisos.TODOS

    @property
    def ejemplos(self) -> list[str]:
        """Consultas de ejemplo para quien recibe una orientación, solo de los tipos que puede
        hacer.
        """
        if not self.motivo:
            return []
        return [e for e in EJEMPLOS_DE_CONSULTA if analizar(e).tipo in self.permitidos]


def _orientacion(motivo: MotivoOrientacion, texto: str, permisos_: Permisos) -> _Resultado:
    return _Resultado(
        EstadoConsulta.ORIENTACION,
        mensaje=mensaje_de(motivo, texto),
        motivo=motivo,
        permitidos=permisos_.permitidos,
    )


def _no_permitido(tipo: TipoPregunta, permisos_: Permisos) -> _Resultado:
    """No se responde y se indica qué tipos sí tiene su rol."""
    return _Resultado(
        EstadoConsulta.ORIENTACION,
        mensaje=permisos_.mensaje(tipo),
        motivo=MotivoOrientacion.TIPO_NO_PERMITIDO,
        permitidos=permisos_.permitidos,
    )


def procesar_consulta(
    db: Session,
    identidad: Identidad,
    datos: ConsultaRequest,
    catalogo: FuenteCatalogo,
) -> ConsultaOut:
    """Procesa una consulta en lenguaje natural.

    Todo corre dentro del tiempo máximo de la consulta y se mide con su intención, también
    si se corta o falla.
    """
    segundos = config.SEGUNDOS_MAXIMOS_CONSULTA
    with medir_consulta(identidad) as medicion:
        medicion.intencion = _intencion_del_texto(datos)
        try:
            with plazo(segundos):
                salida = _procesar(db, identidad, datos, catalogo)
        except (TiempoAgotado, MCPTiempoAgotado) as error:
            logger.warning("Consulta cancelada por superar %g s: %s", segundos, error)
            raise TiempoAgotado(segundos) from error
        medicion.terminar(salida)
        return salida


def _intencion_del_texto(datos: ConsultaRequest) -> IntencionConsulta:
    """Intención según el texto, antes de buscar nada: el motivo si no es una consulta o el
    tipo de pregunta. Al terminar se precisa con lo que se respondió.
    """
    motivo = None if datos.especie_id else interpretar(datos.texto)
    if motivo is not None:
        return IntencionConsulta(motivo)
    return IntencionConsulta(analizar(datos.texto).tipo)


def _procesar(
    db: Session,
    identidad: Identidad,
    datos: ConsultaRequest,
    catalogo: FuenteCatalogo,
) -> ConsultaOut:
    limite = limite_de(identidad)
    usadas = consultas_del_periodo(db, identidad)

    # Elegir la especie de una consulta ambigua ya guardada.
    if datos.consulta_id is not None:
        return _resolver_pendiente(db, identidad, datos, catalogo, limite, usadas)

    if usadas >= limite:
        raise _limite_alcanzado(identidad, limite)

    resultado = _resolver(datos, catalogo, permisos.de(db, identidad))

    # Si el tiempo se acabó mientras se buscaba, se corta aquí, antes de guardar o contar
    # nada.
    verificar_plazo()

    estado, respuesta = resultado.estado, resultado.respuesta
    if respuesta is not None:
        respuesta = preferencias.aplicar(respuesta, preferencias.de(db, identidad.usuario))
    resuelta = estado == EstadoConsulta.RESUELTA
    restantes = max(limite - usadas - (1 if resuelta else 0), 0)

    # --- visitante: se cuenta, pero no se guarda -----------------------------------
    if identidad.usuario is None:
        if resuelta and identidad.anon_id is not None:
            registrar_consumo_anonimo(db, identidad.anon_id)
        return ConsultaOut(
            estado=estado,
            texto=datos.texto,
            respuesta=respuesta,
            candidatos=resultado.candidatas,
            mensaje=resultado.mensaje,
            motivo=resultado.motivo,
            ejemplos=resultado.ejemplos,
            consultas_restantes=restantes,
        )

    # --- cuenta registrada: se guarda en su conversación ----------------------------
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
        candidatos=[c.model_dump(mode="json") for c in resultado.candidatas] or None,
        mensaje=resultado.mensaje,
        motivo=resultado.motivo,
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
        candidatos=resultado.candidatas,
        mensaje=resultado.mensaje,
        motivo=resultado.motivo,
        ejemplos=resultado.ejemplos,
        realizada_en=consulta.realizada_en,
        consultas_restantes=restantes,
    )


def _resolver(datos: ConsultaRequest, catalogo: FuenteCatalogo, permisos_: Permisos) -> _Resultado:
    """Qué se responde: orientación, sin coincidencias, ambigua o resuelta."""
    # Si no es una consulta, se orienta sin buscar. Con 'especie_id' el usuario ya eligió
    # entre candidatas.
    motivo = None if datos.especie_id else interpretar(datos.texto)
    if motivo is not None:
        return _orientacion(motivo, datos.texto, permisos_)

    # Un tipo no permitido no se busca: no se llama a CR-BioLM ni se ofrecen candidatas.
    tipo = analizar(datos.texto).tipo
    if not permisos_.permite(tipo):
        return _no_permitido(tipo, permisos_)

    candidatas = _identificar_especies(datos, catalogo)
    if not candidatas:
        # Sin especie y sin nada sobre plantas: fuera de tema. Sin especie y sobre la flora
        # de otro país: fuera de alcance.
        if fuera_de_tema(datos.texto) or fuera_de_costa_rica(datos.texto):
            return _orientacion(MotivoOrientacion.FUERA_DE_TEMA, datos.texto, permisos_)
        return _Resultado(EstadoConsulta.SIN_COINCIDENCIAS, mensaje=MENSAJE_SIN_COINCIDENCIAS)
    incompleta = next((c.frase_incompleta for c in candidatas if c.frase_incompleta), None)
    if incompleta:
        # "cedro amargo" no existe, pero "amargo" sí: se pregunta antes de responder con
        # otra planta, aunque haya una sola candidata.
        mensaje = MENSAJE_NOMBRE_INCOMPLETO.format(frase=incompleta)
        return _Resultado(EstadoConsulta.AMBIGUA, candidatas=candidatas, mensaje=mensaje)
    if len(candidatas) > 1:
        # Varias coincidencias: el usuario elige.
        return _Resultado(EstadoConsulta.AMBIGUA, candidatas=candidatas, mensaje=MENSAJE_AMBIGUA)
    respuesta = _construir_respuesta(catalogo, candidatas[0].id, datos.texto)
    # Con el vocabulario de CR-BioLM el tipo puede precisarse.
    if not permisos_.permite(respuesta.tipo):
        return _no_permitido(respuesta.tipo, permisos_)
    return _Resultado(EstadoConsulta.RESUELTA, respuesta=respuesta)


def _identificar_especies(
    datos: ConsultaRequest, catalogo: FuenteCatalogo
) -> list[EspecieCandidata]:
    """Las especies candidatas: la que eligió el usuario, o las que reconoce el texto."""
    if not datos.especie_id:
        return catalogo.buscar_especies(datos.texto)
    # El usuario ya eligió entre las candidatas.
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
    """Resuelve una consulta ambigua guardada con la especie elegida.

    Se actualiza la misma fila: la conversación muestra una sola consulta y cuenta una sola
    vez, aunque se elija días después. La fila se bloquea para que dos clics seguidos no la
    cuenten dos veces.
    """
    if identidad.usuario is None:
        raise SolicitudInvalida("Solo las cuentas registradas guardan consultas pendientes.")
    if not datos.especie_id:
        raise SolicitudInvalida("Falta la especie elegida.")
    consulta = _consulta_pendiente(db, identidad.usuario.id, datos.consulta_id, datos.especie_id)
    if usadas >= limite:
        raise _limite_alcanzado(identidad, limite, pendiente=True)

    respuesta = _respuesta_permitida(db, identidad, catalogo, datos.especie_id, consulta.texto)
    respuesta = preferencias.aplicar(respuesta, preferencias.de(db, identidad.usuario))
    verificar_plazo()  # antes de resolverla y contarla
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


def _consulta_pendiente(
    db: Session, usuario_id: int, consulta_id: int | None, especie_id: str
) -> Consulta:
    """La consulta ambigua de esta cuenta, bloqueada, si `especie_id` es una de sus opciones."""
    consulta = (
        db.query(Consulta)
        .filter(Consulta.id == consulta_id, Consulta.usuario_id == usuario_id)
        .with_for_update()
        .first()
    )
    if consulta is None:
        raise NoEncontrado("La consulta no existe.")
    if consulta.estado != EstadoConsulta.AMBIGUA:
        raise Conflicto("Esta consulta ya se resolvió.")
    ofrecidas = {c["id"] for c in (consulta.candidatos or [])}
    if especie_id not in ofrecidas:
        raise SolicitudInvalida("La especie elegida no es una de las opciones de esta consulta.")
    return consulta


def _respuesta_permitida(
    db: Session, identidad: Identidad, catalogo: FuenteCatalogo, especie_id: str, texto: str
) -> RespuestaConsulta:
    """Respuesta de una pendiente, si su tipo sigue permitido.

    Si los permisos cambiaron y ya no lo está, se rechaza sin resolverla ni contarla y
    queda pendiente.
    """
    permisos_ = permisos.de(db, identidad)
    tipo = analizar(texto).tipo
    if not permisos_.permite(tipo):
        raise AccesoDenegado(permisos_.mensaje(tipo))
    respuesta = _construir_respuesta(catalogo, especie_id, texto)
    if not permisos_.permite(respuesta.tipo):
        raise AccesoDenegado(permisos_.mensaje(respuesta.tipo))
    return respuesta


def _limite_alcanzado(
    identidad: Identidad, limite: int, pendiente: bool = False
) -> LimiteAlcanzado:
    """Aviso con el límite y cuándo se restablece."""
    periodo = periodo_de(identidad)
    cuando = cuando_se_restablece(fin_del_periodo(periodo))
    consultas = "1 consulta" if limite == 1 else f"{limite} consultas"
    if identidad.es_anonimo:
        return LimiteAlcanzado(
            f"Alcanzaste el límite de {consultas} por día sin cuenta. Se restablece {cuando}. "
            "Crea una cuenta para obtener más consultas."
        )
    alcanzado = f"Alcanzaste tu límite de {consultas} {POR_PERIODO[periodo]}."
    if pendiente:
        return LimiteAlcanzado(
            f"{alcanzado} La consulta queda pendiente: podrás elegir la especie cuando "
            f"se restablezca tu límite, {cuando}."
        )
    return LimiteAlcanzado(f"{alcanzado} Se restablece {cuando}.")


def cuando_se_restablece(momento: datetime) -> str:
    """'el 20/10/2026 a las 00:00 (hora de Costa Rica)'. Los periodos empiezan a las 00:00."""
    return f"el {fecha_para_mostrar(momento)} a las 00:00 (hora de Costa Rica)"


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
    """Conversación donde se guarda la consulta; si no viene, se crea una. La de otra persona
    responde 404, igual que si no existiera.
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
