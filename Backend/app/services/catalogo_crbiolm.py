"""Catálogo de especies con los datos reales de CR-BioLM, por MCP.

Implementa la interfaz `FuenteCatalogo` (services/catalogo.py) con las
herramientas del servidor de CR-BioLM. Todo es L0/L1 salvo la redacción de la
respuesta (RR_49), que usa el LLM de CR-BioLM (answer_question, L2).

    buscar_especies      -> get_species (provisional, ver el método)
    obtener_especie      -> get_species
    construir_respuesta  -> get_species + get_occurrence_points + get_species_map_image
                            + get_relevant_passage (si pregunta algo concreto)
                            + answer_question (RR_49, si hay pregunta)
    obtener_ficha        -> get_species + get_occurrence_points + get_species_map_image
    obtener_mapa         -> el mapa en memoria, o lo mismo que la ficha

Todo se combina en un contexto único por especie (services/contexto_especie.py,
RR_45), del que salen la respuesta y la ficha.

Mapas: todos vienen de CR-BioLM (el PNG de render_species_map). Si CR-BioLM no
genera mapa para una especie, la respuesta sale sin mapa; el backend nunca
dibuja uno propio.

Antes de armar la respuesta, los datos de cada fuente se validan
(services/validacion_datos.py):

- RR_60: solo se usa lo que corresponde exactamente a la especie pedida; el
  resto se descarta.
- RR_43: con menos de MINIMO_REGISTROS_MAPA registros válidos no se pide ni se
  muestra mapa, y la respuesta lo avisa en `avisos`.
- RR_58: si CR-BioLM no logra consultar GBIF, se reintenta hasta
  GBIF_REINTENTOS veces con una espera entre intentos. Si todos fallan, la
  respuesta sale con los datos del Manual, sin registros ni mapa, y lo avisa.

Según la pregunta (services/intencion.py):

- RR_41: el tipo de pregunta (distribución, descripción...) elige el texto.
  GBIF y el mapa se piden siempre que existan (RR_52, RR_46, RR_59).
- RR_44: si pregunta algo concreto, el texto es el fragmento del Manual que lo
  responde (búsqueda semántica en CR-BioLM); si no, el texto de la ficha.
- RR_49: si hay pregunta, el texto es la respuesta que redacta el LLM de
  CR-BioLM, con las citas del Manual dentro. Se usa solo si responde sobre la
  misma especie (RR_60); si falla, tarda más de SEGUNDOS_MAXIMOS_REDACCION_IA o
  responde otra cosa, se usa el texto del Manual de los puntos anteriores.

Se activa con CATALOGO=crbiolm en el .env (ver config.py). Los errores de
conexión con CR-BioLM y el tiempo agotado no se atrapan aquí: los maneja el
servicio de consultas (RR_38) y, más adelante, RR_05. Las excepciones son GBIF
(RR_58, arriba), el mapa, el fragmento (RR_44) y la redacción del LLM (RR_49):
si esas herramientas fallan, la respuesta sale igual, sin mapa o con el texto
de la ficha.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import replace
from itertools import pairwise
from typing import Any

from .. import config
from ..sanitizacion import con_nombre_canonico, normalizar
from ..schemas.consulta import (
    EspecieCandidata,
    FichaEspecie,
    RegistroPresencia,
    RespuestaConsulta,
)
from ..tiempo import alcanza_para_esperar, plazo, segundos_restantes
from . import mcp_cliente
from .contexto_especie import (
    ContextoEspecie,
    Fragmento,
    MapaGenerado,
    Ocurrencias,
    RedaccionIA,
    especie_de_la_cita,
)
from .correccion import corregir_nombres
from .intencion import analizar
from .mcp_cliente import MCPErrorHerramienta, MCPRespuestaInvalida, MCPTiempoAgotado, Sobre
from .regiones import Zona, extraer_zona
from .validacion_datos import alcanza_para_mapa, misma_especie, punto_valido

logger = logging.getLogger("uvicorn.error")

SIN_DATO = "Sin dato"
FUENTE_GBIF = "GBIF"

# Mapas que se guardan en memoria para servirlos en GET /especies/{id}/mapa sin
# volver a pedirlos a CR-BioLM. Cada PNG pesa unos cientos de KB.
MAPAS_EN_MEMORIA = 64

# RR_49: answer_question responde en modo "A (especie)" cuando habla de una
# especie concreta; "B" es una lista de especies y "B→A" un superlativo.
MODO_UNA_ESPECIE = "A"

# RR_49: cuando OpenRouter falla (modelo retirado, sin créditos...), CR-BioLM no
# da error: devuelve como texto "(síntesis no disponible: <excepción>)".
SINTESIS_NO_DISPONIBLE = "(síntesis no disponible"

# RR_49 y RR_38: segundos que se dejan libres después de la redacción del LLM
# para terminar la consulta (guardarla y responder) dentro de su tiempo máximo.
MARGEN_TRAS_REDACCION = 5.0

# Rangos infraespecíficos que el id escribe sin punto ("var", no "var.").
_RANGOS = {"var", "subsp", "f"}


# --- id <-> nombre científico --------------------------------------------------


def a_id(nombre_cientifico: str) -> str:
    """'Quercus costaricensis' -> 'quercus-costaricensis' (formato de ConsultaRequest)."""
    limpio = "".join(c for c in nombre_cientifico.lower() if c.isalnum() or c == " ")
    return "-".join(limpio.split())


def a_nombre(especie_id: str) -> str:
    """'quercus-costaricensis' -> 'Quercus costaricensis' (como lo guarda CR-BioLM)."""
    partes = [f"{p}." if p in _RANGOS else p for p in especie_id.split("-")]
    return " ".join(partes).capitalize()


# --- catálogo -------------------------------------------------------------------


class CatalogoCRBioLM:
    """Catálogo respaldado por el servidor MCP de CR-BioLM."""

    def __init__(self) -> None:
        self._mapas: OrderedDict[str, MapaGenerado] = OrderedDict()
        self._candado = threading.Lock()  # los endpoints corren en varios hilos
        self._nombres_del_catalogo: dict[str, str] | None = None  # RR_23
        self._vocabulario_del_catalogo: dict[str, Any] | None = None  # RR_39

    def buscar_especies(self, texto: str) -> list[EspecieCandidata]:
        """Especies que menciona la consulta: 0 = ninguna, 2+ = ambigua (RR_17).

        PROVISIONAL: solo reconoce nombres científicos (dos palabras seguidas que
        sean una especie del catálogo, sin importar mayúsculas). Identificar la
        especie es del módulo de identificación de Jesús (RR_24, 26, 31, 39 y, en
        el sprint 3, nombres comunes RR_25, sinónimos RR_27, ambigüedad RR_28 y
        varias especies RR_36). Cuando esté listo, este método solo lo llama.

        RR_23: si no reconoce ninguna, corrige los nombres con hasta
        LETRAS_MAXIMAS_CORRECCION letras mal escritas y vuelve a buscar.
        """
        palabras = re.findall(r"[^\W\d_][\w-]*", texto)
        encontradas: dict[str, EspecieCandidata] = {}
        for genero, epiteto in pairwise(palabras):
            # RR_35: los nombres científicos no llevan tildes, así que se quitan
            # antes de buscar ("Quércus" encuentra Quercus).
            manual = self._manual(normalizar(f"{genero} {epiteto}").capitalize())
            if manual is not None:
                candidata = _candidata(manual.valor)
                encontradas.setdefault(candidata.id, candidata)
        if not encontradas:
            corregido = corregir_nombres(texto, self._nombres())
            if corregido != texto:
                return self.buscar_especies(corregido)
        return list(encontradas.values())

    def obtener_especie(self, especie_id: str) -> EspecieCandidata | None:
        manual = self._manual(a_nombre(especie_id))
        return _candidata(manual.valor) if manual else None

    def construir_respuesta(self, especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
        """Respuesta a la consulta, armada desde el contexto de la especie (RR_45).

        RR_49: si hay pregunta, el texto lo redacta el LLM de CR-BioLM.
        """
        nombre = a_nombre(especie_id)
        if texto_consulta and normalizar(nombre) not in normalizar(texto_consulta):
            # RR_23: el Manual y el LLM reciben la pregunta con el nombre corregido.
            texto_consulta = corregir_nombres(texto_consulta, self._nombres())
        # RR_35: y escrito como en el catálogo, sin importar mayúsculas ni tildes.
        # CR-BioLM reconoce la especie de la pregunta solo si está escrita así
        # ("Quercus costaricensis"); si no, la toma como una pregunta por varias
        # especies y la respuesta del LLM no sirve (RR_49).
        texto_consulta = con_nombre_canonico(texto_consulta, nombre)
        contexto = self.contexto(nombre, texto_consulta)
        if contexto is None:
            return None
        contexto = _con_redaccion_ia(contexto, texto_consulta)
        return RespuestaConsulta(
            especie=_candidata(contexto.ficha),
            texto=contexto.texto(),
            elevacion=_elevacion(contexto.ficha),
            registros=contexto.registros,
            total_registros=contexto.total_registros,
            fuentes=contexto.fuentes(),
            mapa=contexto.mapa_especie(_url_del_mapa(contexto.especie)),
            avisos=contexto.avisos,
            geoespacial=contexto.geoespacial,
            tipo=contexto.tipo,
            procedencia=contexto.procedencia(),
        )

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """RR_20. Acepta el id ('quercus-costaricensis') o el nombre científico.

        La ficha no responde una pregunta: trae todo, incluidos registros y mapa.
        """
        contexto = self.contexto(especie if " " in especie.strip() else a_nombre(especie))
        if contexto is None:
            return None
        ficha = contexto.ficha
        return FichaEspecie(
            **_candidata(ficha).model_dump(),
            habitat=", ".join(ficha.get("forest_types") or []) or None,
            elevacion=_elevacion(ficha),
            descripcion=ficha.get("morphology") or ficha.get("distribution_paragraph") or None,
            registros=contexto.registros,
            total_registros=contexto.total_registros,
            fuentes=contexto.fuentes(),
            mapa=contexto.mapa_especie(_url_del_mapa(contexto.especie)),
            avisos=contexto.avisos,
            procedencia=contexto.procedencia(con_texto=False),
        )

    def obtener_mapa(self, especie_id: str) -> bytes | None:
        """PNG del mapa (GET /especies/{id}/mapa)."""
        with self._candado:
            if especie_id in self._mapas:
                self._mapas.move_to_end(especie_id)
                return self._mapas[especie_id].png
        contexto = self.contexto(a_nombre(especie_id))
        return contexto.mapa.png if contexto and contexto.mapa else None

    def contexto(self, nombre: str, pregunta: str = "") -> ContextoEspecie | None:
        """RR_45: toda la información validada de la especie, como un contexto único.
        - RR_41: su tipo, que elige el texto (contexto_especie.py).
        - RR_44: si pregunta algo concreto, se busca el fragmento del Manual.
        - RR_39: si menciona una región o vertiente, los registros y su conteo
          son solo los de esa zona. El mapa sigue siendo el nacional.

        Todo se pide con el nombre de la ficha ya validada (RR_60).
        """
        manual = self._manual(nombre)
        if manual is None:
            return None
        especie = str(manual.valor["species"])
        # RR_29: los tipos de bosque del vocabulario (el de RR_39) también son hábitat.
        intencion = analizar(pregunta, especie, self._vocabulario() if pregunta else None)
        fragmento = _fragmento(especie, pregunta) if intencion.pregunta_especifica else None

        ocurrencias = _ocurrencias(especie)
        avisos: list[str] = []
        mapa = None
        if ocurrencias.sobre is None:
            avisos.append(_aviso_gbif_no_disponible(ocurrencias.intentos))
        elif not alcanza_para_mapa(ocurrencias.total):
            # RR_43: con datos insuficientes ni siquiera se pide el mapa.
            avisos.append(_aviso_pocos_registros(especie, ocurrencias.total))
        else:
            mapa = self._mapa(a_id(especie), especie)
        # RR_39: después de decidir el mapa, que se decide con el total nacional.
        zona = extraer_zona(pregunta, self._vocabulario()) if pregunta else None
        if zona is not None:
            ocurrencias = _en_zona(ocurrencias, zona, especie)
        return ContextoEspecie(manual, ocurrencias, mapa, fragmento, avisos, intencion.tipo)

    def _mapa(self, especie_id: str, nombre: str) -> MapaGenerado | None:
        with self._candado:
            if especie_id in self._mapas:
                self._mapas.move_to_end(especie_id)
                return self._mapas[especie_id]
        mapa = _pedir_mapa(nombre)
        if mapa is not None:
            with self._candado:
                self._mapas[especie_id] = mapa
                while len(self._mapas) > MAPAS_EN_MEMORIA:
                    self._mapas.popitem(last=False)
        return mapa

    def _nombres(self) -> dict[str, str]:
        """RR_23: los nombres del catálogo (normalizado -> como lo guarda CR-BioLM).

        Se piden una sola vez: search_species sin filtros (L0) devuelve todo el
        catálogo. Si CR-BioLM no los da, no se corrige y se piden otra vez en la
        siguiente consulta. Si dos hilos los piden a la vez, no pasa nada.
        """
        if self._nombres_del_catalogo is None:
            try:
                especies = mcp_cliente.llamar("search_species").valor["species"]
                nombres = {normalizar(e["species"]): e["species"] for e in especies}
            except (MCPErrorHerramienta, MCPRespuestaInvalida, KeyError, TypeError):
                logger.warning("RR_23: CR-BioLM no dio el catálogo de nombres; no se corrige")
                return {}
            self._nombres_del_catalogo = nombres
        return self._nombres_del_catalogo

    def _vocabulario(self) -> dict[str, Any] | None:
        """RR_39: las regiones y vertientes del Manual (get_vocabulary, L0), una sola vez.

        Si CR-BioLM no las da, no se filtra por zona y se piden otra vez después.
        """
        if self._vocabulario_del_catalogo is None:
            try:
                valor = mcp_cliente.llamar("get_vocabulary").valor
            except (MCPErrorHerramienta, MCPRespuestaInvalida):
                logger.warning("RR_39: CR-BioLM no dio el vocabulario; no se filtra por zona")
                return None
            if isinstance(valor, dict):
                self._vocabulario_del_catalogo = valor
        return self._vocabulario_del_catalogo

    @staticmethod
    def _manual(nombre: str) -> Sobre | None:
        """La ficha del Manual, o None si la especie no está en el catálogo.

        RR_60: si la ficha que llega es de otra especie, se descarta como si no
        existiera.
        """
        sobre = mcp_cliente.llamar("get_species", name=nombre)
        if not sobre.valor:
            return None
        recibida = sobre.valor.get("species") if isinstance(sobre.valor, dict) else None
        if not misma_especie(nombre, recibida):
            logger.warning(
                "RR_60: se pidió la ficha de %s y llegó la de %r; se descarta", nombre, recibida
            )
            return None
        return sobre


def _url_del_mapa(especie: str) -> str:
    return f"/especies/{a_id(especie)}/mapa"


# --- Manual vectorizado: el fragmento que responde la pregunta (RR_44) --------


def _fragmento(especie: str, pregunta: str) -> Fragmento | None:
    """El fragmento del Manual de la especie que mejor responde la pregunta.

    Usa la herramienta get_relevant_passage de CR-BioLM: búsqueda semántica
    (L1, embeddings locales, sin costo) sobre los fragmentos vectorizados del
    Manual de ESA especie. None si no hay fragmento; entonces la respuesta usa
    el texto de la ficha, como antes de RR_44. Pasa cuando:

    - la herramienta no existe todavía o falla (p. ej. la base de vectores de
      CR-BioLM no está levantada),
    - CR-BioLM no tiene texto vectorizado de la especie,
    - el fragmento es de otra especie (RR_60, RR_45 criterio 1).

    El tiempo agotado sí se deja pasar: es el límite de la consulta (RR_38).
    """
    try:
        sobre = mcp_cliente.llamar("get_relevant_passage", species=especie, question=pregunta)
    except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
        logger.warning("RR_44: sin fragmento del Manual para %s: %s", especie, error)
        return None
    valor = sobre.valor if isinstance(sobre.valor, dict) else None
    if not valor:
        logger.info("RR_44: CR-BioLM no dio fragmento de %s: %s", especie, sobre.advertencia)
        return None
    if not misma_especie(especie, valor.get("species")):
        logger.warning(
            "RR_60: se pidió un fragmento de %s y llegó de %r; se descarta",
            especie,
            valor.get("species"),
        )
        return None
    pasajes = valor.get("passages") or []
    mejor = pasajes[0] if pasajes and isinstance(pasajes[0], dict) else {}
    texto = str(mejor.get("text") or "").strip()
    if not texto:
        return None
    return Fragmento(texto=texto, seccion=str(mejor.get("section") or ""))


# --- RR_49: respuesta redactada por el LLM de CR-BioLM ------------------------


def _con_redaccion_ia(contexto: ContextoEspecie, pregunta: str) -> ContextoEspecie:
    """El contexto con la respuesta que redacta el LLM, si se pudo obtener (RR_49).

    Sin pregunta no hay nada que redactar: queda el texto del Manual.
    """
    if not pregunta.strip():
        return contexto
    redaccion = _redaccion_ia(contexto.especie, pregunta)
    return replace(contexto, redaccion=redaccion) if redaccion else contexto


def _redaccion_ia(especie: str, pregunta: str) -> RedaccionIA | None:
    """La respuesta de answer_question sobre `especie`, o None para usar el Manual.

    Usa el LLM de CR-BioLM (L2): necesita OPENROUTER_API_KEY en el .env de
    CR-BioLM, no en el de este proyecto. Es None cuando:

    - no queda tiempo en la consulta para esperarlo (RR_38),
    - la herramienta falla (sin llave, límite de uso del modelo gratuito...),
    - tarda más de SEGUNDOS_MAXIMOS_REDACCION_IA: a diferencia de las otras
      herramientas, su tiempo agotado no corta la consulta, solo se descarta,
    - responde otra cosa que no es la especie pedida (ver `_validar_redaccion`).
    """
    segundos = _segundos_para_la_redaccion()
    if segundos is None:
        logger.info("RR_49: no queda tiempo para pedir la respuesta al LLM (%s)", especie)
        return None
    try:
        with plazo(segundos):
            sobre = mcp_cliente.llamar("answer_question", question=pregunta)
    except (MCPErrorHerramienta, MCPRespuestaInvalida, MCPTiempoAgotado) as error:
        logger.warning("RR_49: CR-BioLM no redactó la respuesta de %s: %s", especie, error)
        return None
    return _validar_redaccion(especie, sobre)


def _segundos_para_la_redaccion() -> float | None:
    """Tiempo para el LLM sin pasarse del de la consulta (RR_38); None si no alcanza."""
    segundos = config.SEGUNDOS_MAXIMOS_REDACCION_IA
    restantes = segundos_restantes()
    if restantes is not None:
        segundos = min(segundos, restantes - MARGEN_TRAS_REDACCION)
    return segundos if segundos >= 1 else None


def _validar_redaccion(especie: str, sobre: Sobre) -> RedaccionIA | None:
    """RR_49 y RR_60: solo se acepta una respuesta sobre la especie pedida, con citas.

    answer_question decide por su cuenta de qué habla la pregunta, así que se
    exige que haya respondido sobre UNA especie (modo A) y que todas sus citas
    del Manual sean de la especie que identificó el backend.
    """
    valor = sobre.valor if isinstance(sobre.valor, dict) else {}
    texto = str(valor.get("text") or "").strip()
    if not sobre.es_suficiente or not texto:
        logger.info("RR_49: el LLM no dio respuesta para %s: %s", especie, sobre.advertencia)
        return None
    if texto.startswith(SINTESIS_NO_DISPONIBLE):
        logger.warning("RR_49: el LLM de CR-BioLM falló para %s: %s", especie, texto)
        return None
    modo = str(valor.get("mode") or "")
    if not modo.startswith(MODO_UNA_ESPECIE):
        logger.info("RR_49: el LLM respondió en modo %r, no sobre %s", modo, especie)
        return None
    citas = [str(c).strip() for c in valor.get("citations") or [] if str(c).strip()]
    citadas = [especie_de_la_cita(c) for c in citas]
    if not citadas or not all(misma_especie(especie, c) for c in citadas):
        logger.warning(
            "RR_60: el LLM respondió sobre %s con citas de %r; se descarta", especie, citadas
        )
        return None
    return RedaccionIA(texto=texto, citas=citas)


# --- GBIF: reintentos (RR_58) y validación de los registros (RR_60) -------------


def _ocurrencias(especie: str) -> Ocurrencias:
    """Los registros de GBIF de la especie, sin los puntos inválidos (RR_60)."""
    sobre, intentos = _consultar_gbif(especie)
    if sobre is None:
        return Ocurrencias(None, [], 0, intentos)
    valor = sobre.valor if isinstance(sobre.valor, dict) else {}
    puntos = valor.get("points") or []
    validos = [p for p in puntos if punto_valido(p)]
    descartados = len(puntos) - len(validos)
    if descartados:
        logger.warning(
            "RR_60: se descartaron %d de %d registros de GBIF de %s (coordenadas inválidas)",
            descartados,
            len(puntos),
            especie,
        )
    total = max(int(valor.get("n") or 0) - descartados, len(validos))
    return Ocurrencias(sobre, [_registro(p) for p in validos], total, intentos)


def _en_zona(ocurrencias: Ocurrencias, zona: Zona, especie: str) -> Ocurrencias:
    """RR_39: solo los registros válidos (RR_60) de la zona, con su conteo.

    CR-BioLM entrega a lo sumo 500 puntos por defecto; si cortó, se le piden
    todos para que el conteo de la zona sea completo.
    """
    if ocurrencias.sobre is None or not isinstance(ocurrencias.sobre.valor, dict):
        return ocurrencias
    valor = ocurrencias.sobre.valor
    if valor.get("truncated"):
        try:
            completo = mcp_cliente.llamar(
                "get_occurrence_points", species=especie, limit=int(valor.get("n") or 0)
            ).valor
            valor = completo if isinstance(completo, dict) else valor
        except (MCPErrorHerramienta, MCPRespuestaInvalida):
            logger.warning("RR_39: no se pudieron pedir todos los puntos de %s", especie)
    puntos = [p for p in valor.get("points") or [] if punto_valido(p) and zona.incluye(p)]
    return replace(ocurrencias, registros=[_registro(p) for p in puntos], total=len(puntos))


def _consultar_gbif(especie: str) -> tuple[Sobre | None, int]:
    """get_occurrence_points con reintentos (RR_58): (sobre o None, intentos hechos).

    Se reintenta cuando la herramienta falla dentro de CR-BioLM (GBIF caído,
    error de red, respuesta mal formada). No se reintenta si CR-BioLM está
    caído ni si se agotó el tiempo de la consulta (RR_38): esos errores suben.
    """
    intentos = config.GBIF_REINTENTOS + 1
    espera = config.GBIF_ESPERA_REINTENTO_SEGUNDOS
    for intento in range(1, intentos + 1):
        try:
            return mcp_cliente.llamar("get_occurrence_points", species=especie), intento
        except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
            logger.warning(
                "RR_58: GBIF no respondió para %s (intento %d de %d): %s",
                especie,
                intento,
                intentos,
                error,
            )
            if intento == intentos or not alcanza_para_esperar(espera):
                logger.error("RR_58: GBIF no respondió para %s tras %d intentos", especie, intento)
                return None, intento
            time.sleep(espera)
    raise AssertionError("inalcanzable")  # el ciclo siempre retorna


def _aviso_gbif_no_disponible(intentos: int) -> str:
    veces = "1 intento" if intentos == 1 else f"{intentos} intentos"
    return (
        f"No se pudo consultar GBIF ({veces}). La respuesta incluye solo los datos del "
        "Manual, sin registros de presencia ni mapa. Puedes intentarlo de nuevo más tarde."
    )


def _aviso_pocos_registros(especie: str, total: int) -> str:
    """RR_43 criterio 2: por qué no hay mapa."""
    if total == 0:
        return f"GBIF no tiene registros válidos de {especie} en Costa Rica, así que no hay mapa."
    registros = "1 registro válido" if total == 1 else f"{total} registros válidos"
    return (
        f"Solo hay {registros} de {especie} en Costa Rica y se necesitan al menos "
        f"{config.MINIMO_REGISTROS_MAPA} para generar el mapa, así que no se muestra."
    )


# --- conversión de los datos de CR-BioLM a los esquemas del proyecto ------------


def _pedir_mapa(nombre: str) -> MapaGenerado | None:
    """El mapa de CR-BioLM, o None si no lo genera.

    Si la herramienta falla, la respuesta sale sin mapa en lugar de fallar
    entera. El tiempo agotado sí se deja pasar: es el límite de la consulta (RR_38).
    """
    try:
        sobre = mcp_cliente.llamar("get_species_map_image", species=nombre)
    except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
        logger.warning("CR-BioLM no generó el mapa de %s: %s", nombre, error)
        return None
    valor = sobre.valor or {}
    if not valor.get("png_base64"):
        return None
    if not _mapa_de_la_especie(nombre, valor):
        return None
    capas = [c.strip() for c in str(valor.get("layer_summary", "")).split("|") if c.strip()]
    return MapaGenerado(
        png=base64.b64decode(valor["png_base64"]),
        capas=capas,
        puntos=int(valor.get("n_pts") or 0),
        advertencia=sobre.advertencia or None,
    )


def _mapa_de_la_especie(nombre: str, valor: dict[str, Any]) -> bool:
    """RR_54 criterios 1 y 2: el mapa que llega es de la especie pedida.

    El mapa se pide con el nombre ya validado (RR_60). Si además CR-BioLM dice
    de qué especie es (`species`) y no coincide, se descarta: es preferible no
    mostrar mapa que mostrar el de otra especie. Los guiones bajos se tratan
    como espacios, porque CR-BioLM los usa en algunos nombres.
    """
    recibida = valor.get("species")
    if recibida is None:
        return True
    if isinstance(recibida, str) and misma_especie(nombre, recibida.replace("_", " ")):
        return True
    logger.warning("RR_54: se pidió el mapa de %s y llegó el de %r; se descarta", nombre, recibida)
    return False


def _candidata(ficha: dict[str, Any]) -> EspecieCandidata:
    comunes = ficha.get("common_names") or []
    return EspecieCandidata(
        id=a_id(ficha["species"]),
        nombre_comun=comunes[0] if comunes else None,
        nombre_cientifico=ficha["species"],
        familia=ficha.get("family") or SIN_DATO,
    )


def _elevacion(ficha: dict[str, Any]) -> str | None:
    minima, maxima = ficha.get("elev_min"), ficha.get("elev_max")
    if minima is not None and maxima is not None:
        return f"{minima} – {maxima} msnm"
    if minima is not None or maxima is not None:
        return f"{minima if minima is not None else maxima} msnm"
    return None


def _registro(punto: dict[str, Any]) -> RegistroPresencia:
    """Un punto de GBIF ya limpiado por CR-BioLM (RR_42 criterio 3) y validado (RR_60)."""
    return RegistroPresencia(
        localidad=punto.get("region") or SIN_DATO,
        fecha=_fecha(punto),
        latitud=punto["lat"],
        longitud=punto["lon"],
        elevacion_m=punto.get("elev_m"),
        fuente=FUENTE_GBIF,
    )


def _fecha(punto: dict[str, Any]) -> str:
    """La fecha del registro en GBIF ('2019-03-14', '2019-03' o '2019'), o SIN_DATO.

    CR-BioLM la entrega en 'date'; si no viene (registros sin fecha o una versión
    de CR-BioLM que todavía no la manda), se muestra "Sin dato".
    """
    fecha = punto.get("date")
    if not isinstance(fecha, str) or not fecha.strip():
        return SIN_DATO
    return fecha.split("/")[0].split("T")[0].strip()
