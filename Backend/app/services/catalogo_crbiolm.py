"""Catálogo de especies con los datos reales de CR-BioLM, por MCP.

Implementa `FuenteCatalogo` (services/catalogo.py) con las herramientas de CR-BioLM:

  buscar_especies      -> get_species; si no hay nombre científico, resolve_common_name y
  list_synonyms
  obtener_especie      -> get_species
  construir_respuesta  -> get_species + get_occurrence_points + get_species_map_image +
  get_relevant_passage (si pregunta algo concreto) + answer_question (si hay pregunta)
  obtener_ficha        -> get_species + get_occurrence_points + get_species_map_image
  obtener_mapa         -> el mapa en memoria, o lo mismo que la ficha

Todo se combina en un contexto único por especie (services/contexto_especie.py). Los mapas
vienen siempre de CR-BioLM; si no genera uno, la respuesta sale sin mapa.

Antes de armar la respuesta se validan los datos (services/validacion_datos.py):

- Solo se usa lo que corresponde exactamente a la especie pedida.
- Con menos de MINIMO_REGISTROS_MAPA registros válidos no se pide mapa y se avisa en
  `avisos`.
- Si CR-BioLM no logra consultar GBIF, se reintenta hasta GBIF_REINTENTOS veces. Si todos
  fallan, la respuesta sale con los datos del Manual, sin registros ni mapa.
- CR-BioLM guarda los registros de GBIF y los actualiza cada cierto tiempo
  (MPCR_GBIF_CACHE_MAX_DAYS, en su .env); la respuesta muestra cuándo se descargaron y
  avisa si son antiguos.

El texto depende de la pregunta (services/intencion.py): la respuesta redactada por el LLM
de CR-BioLM con citas del Manual, si responde sobre la misma especie y a tiempo; si no, el
fragmento del Manual que responde la pregunta o el texto de la ficha.

Se activa con CATALOGO=crbiolm. Los errores de conexión y el tiempo agotado los maneja el
servicio de consultas; si fallan GBIF, el mapa, el fragmento o el LLM, la respuesta sale
igual con lo disponible.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import UTC, datetime
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
from ..tiempo import alcanza_para_esperar, fecha_para_mostrar, plazo, segundos_restantes
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
from .nombres_comunes import Frase, en_singular, frase_completa, frases_candidatas
from .regiones import Zona, extraer_zona
from .validacion_datos import alcanza_para_mapa, misma_especie, punto_valido

logger = logging.getLogger("uvicorn.error")

SIN_DATO = "Sin dato"
FUENTE_GBIF = "GBIF"

# Mapas que se guardan en memoria para servirlos en GET /especies/{id}/mapa sin
# volver a pedirlos a CR-BioLM. Cada PNG pesa unos cientos de KB.
MAPAS_EN_MEMORIA = 64

# answer_question responde en modo "A (especie)" cuando habla de una especie concreta; "B"
# es una lista de especies y "B→A" un superlativo.
MODO_UNA_ESPECIE = "A"

# Cuando OpenRouter falla, CR-BioLM no da error: devuelve como texto "(síntesis no
# disponible: <excepción>)".
SINTESIS_NO_DISPONIBLE = "(síntesis no disponible"

# Segundos que se reservan después de la redacción del LLM para guardar y responder dentro
# del tiempo máximo de la consulta.
MARGEN_TRAS_REDACCION = 5.0

# Rangos infraespecíficos que el id escribe sin punto ("var", no "var.").
_RANGOS = {"var", "subsp", "f"}

# Una palabra de la consulta: letras y guiones.
_PALABRA = re.compile(r"[^\W\d_][\w-]*")


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
        self._nombres_del_catalogo: dict[str, str] | None = None
        self._familias_del_catalogo: dict[str, str] = {}
        self._vocabulario_del_catalogo: dict[str, Any] | None = None
        self._sinonimos_del_catalogo: dict[str, list[EspecieCandidata]] | None = None

    def buscar_especies(self, texto: str) -> list[EspecieCandidata]:
        """Especies que menciona la consulta: 0 = ninguna, 2+ = ambigua.

        En orden; cada paso solo si el anterior no reconoció ninguna:

        1. Nombres científicos: dos palabras seguidas que sean una especie del catálogo.
        2. Los mismos, corrigiendo hasta LETRAS_MAXIMAS_CORRECCION letras mal escritas.
        3. Nombres comunes, con resolve_common_name.
        4. Sinónimos científicos ("Bombax pentandrum"), con list_synonyms.
        5. Solo un género con varias especies ("Quercus"): se ofrecen algunas para elegir.

        Con nombres científicos se buscan además los nombres comunes del resto de la
        consulta ("el cocobolo y Quercus oleoides"). Un nombre común que nombra a una de
        esas especies no se agrega: es la misma planta.
        """
        buscado = texto
        encontradas, ocupadas = self._nombres_cientificos(texto)
        if not encontradas:
            corregido = corregir_nombres(texto, self._nombres())
            if corregido != texto:
                buscado = corregido
                encontradas, ocupadas = self._nombres_cientificos(corregido)
        if encontradas:
            ids = {e.id for e in encontradas}
            otras = _por_nombre_comun(buscado, ocupadas=ocupadas, ya_nombradas=ids)
            return [*encontradas, *(c for c in otras if c.id not in ids)]
        return _por_nombre_comun(texto) or self._por_sinonimo(texto) or self._por_genero(texto)

    def _nombres_cientificos(self, texto: str) -> tuple[list[EspecieCandidata], list[Frase]]:
        """Las especies con su nombre científico en `texto`, y dónde están escritas."""
        encontradas: dict[str, EspecieCandidata] = {}
        ocupadas: list[Frase] = []
        for genero, epiteto in pairwise(_PALABRA.finditer(texto)):
            # Los nombres científicos no llevan tildes: se quitan antes de buscar ("Quércus"
            # encuentra Quercus).
            manual = self._manual(normalizar(f"{genero.group()} {epiteto.group()}").capitalize())
            if manual is not None:
                candidata = _candidata(manual.valor)
                encontradas.setdefault(candidata.id, candidata)
                inicio, fin = genero.start(), epiteto.end()
                ocupadas.append(Frase(texto[inicio:fin], inicio, fin))
        return list(encontradas.values()), ocupadas

    def _por_genero(self, texto: str) -> list[EspecieCandidata]:
        """Especies del primer género del Manual que nombra la consulta.

        Solo si el género tiene dos o más especies. Se ofrecen las primeras
        GENERO_OPCIONES_MAXIMAS en orden alfabético, sin los nombres que no se pueden pedir
        por su id ("Ilex sp. 1").
        """
        nombres = sorted(n for n in self._nombres().values() if a_nombre(a_id(n)) == n)
        for palabra in _PALABRA.findall(texto):
            genero = normalizar(palabra)
            especies = [n for n in nombres if normalizar(n.split()[0]) == genero]
            if len(especies) > 1:
                return [self._de_la_lista(n) for n in especies[: config.GENERO_OPCIONES_MAXIMAS]]
        return []

    def _por_sinonimo(self, texto: str) -> list[EspecieCandidata]:
        """Especies de los sinónimos científicos de la consulta."""
        sinonimos = self._sinonimos()
        encontradas: dict[str, EspecieCandidata] = {}
        for genero, epiteto in pairwise(_PALABRA.findall(texto)):
            for candidata in sinonimos.get(normalizar(f"{genero} {epiteto}"), []):
                encontradas.setdefault(candidata.id, candidata)
        return list(encontradas.values())

    def _con_sinonimo(self, texto: str, nombre: str) -> tuple[str, list[str]]:
        """La pregunta con `nombre` junto al sinónimo que la nombró, y el aviso. Sin aviso si
        el sinónimo es de varias especies: el usuario eligió.
        """
        if normalizar(nombre) in normalizar(texto):
            return texto, []
        sinonimos = self._sinonimos()
        for genero, epiteto in pairwise(_PALABRA.finditer(texto)):
            especies = sinonimos.get(normalizar(f"{genero.group()} {epiteto.group()}"), [])
            if any(c.nombre_cientifico == nombre for c in especies):
                pregunta = f"{texto[: epiteto.end()]} ({nombre}){texto[epiteto.end() :]}"
                frase = texto[genero.start() : epiteto.end()]
                return pregunta, [_aviso_de_sinonimo(frase, nombre)] if len(especies) == 1 else []
        return texto, []

    def _de_la_lista(self, nombre: str) -> EspecieCandidata:
        """Una especie del catálogo, con los datos de search_species (sin pedir su ficha)."""
        return EspecieCandidata(
            id=a_id(nombre),
            nombre_comun=None,
            nombre_cientifico=nombre,
            familia=self._familias_del_catalogo.get(nombre) or SIN_DATO,
        )

    def obtener_especie(self, especie_id: str) -> EspecieCandidata | None:
        manual = self._manual(a_nombre(especie_id))
        return _candidata(manual.valor) if manual else None

    def construir_respuesta(self, especie_id: str, texto_consulta: str) -> RespuestaConsulta | None:
        """Respuesta a la consulta, armada desde el contexto de la especie. Si hay pregunta,
        el texto lo redacta el LLM de CR-BioLM.
        """
        nombre = a_nombre(especie_id)
        interpretacion: list[str] = []
        nombre_comun: str | None = None
        if texto_consulta and normalizar(nombre) not in normalizar(texto_consulta):
            # El Manual y el LLM reciben la pregunta con el nombre corregido...
            texto_consulta = corregir_nombres(texto_consulta, self._nombres())
            # ...con el científico al lado si la nombró por su nombre común...
            usado = _con_nombre_comun(texto_consulta, nombre)
            texto_consulta, interpretacion = usado.pregunta, list(usado.avisos)
            nombre_comun = usado.nombre_comun
            # ...con el nombre del Manual al lado si la nombró por un sinónimo...
            texto_consulta, aviso_sinonimo = self._con_sinonimo(texto_consulta, nombre)
            interpretacion += aviso_sinonimo
            # ...con la especie elegida si nombró solo el género...
            texto_consulta = _con_especie_del_genero(texto_consulta, nombre)
        # ...solo con la parte de esta especie si nombra varias, también cuando las otras
        # están dichas por su nombre común...
        otras = _otras_por_nombre_comun(texto_consulta, nombre, self._nombres())
        texto_consulta = _pregunta_de_la_especie(texto_consulta, nombre, self._nombres(), otras)
        # ...y escrita como en el catálogo. CR-BioLM reconoce la especie de la pregunta solo
        # si está escrita así ("Quercus costaricensis"); si no, la toma como una pregunta
        # por varias especies.
        texto_consulta = con_nombre_canonico(texto_consulta, nombre)
        contexto = self.contexto(nombre, texto_consulta)
        if contexto is None:
            return None
        contexto = _con_redaccion_ia(contexto, texto_consulta)
        especie = _candidata(contexto.ficha)
        if nombre_comun:
            # Nombre común con el que la buscó el usuario.
            especie = especie.model_copy(update={"nombre_comun": nombre_comun})
        return RespuestaConsulta(
            especie=especie,
            texto=contexto.texto(),
            elevacion=_elevacion(contexto.ficha),
            registros=contexto.registros,
            total_registros=contexto.total_registros,
            fuentes=contexto.fuentes(),
            mapa=contexto.mapa_especie(_url_del_mapa(contexto.especie)),
            avisos=[*interpretacion, *contexto.avisos, *contexto.avisos_del_texto()],
            geoespacial=contexto.geoespacial,
            tipo=contexto.tipo,
            procedencia=contexto.procedencia(),
            registros_actualizados_en=contexto.registros_actualizados_en,
        )

    def obtener_ficha(self, especie: str) -> FichaEspecie | None:
        """Ficha de la especie, por id ('quercus-costaricensis') o nombre científico. Trae
        todo, incluidos registros y mapa.
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
            registros_actualizados_en=contexto.registros_actualizados_en,
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
        """Información validada de la especie, como un contexto único.

        - Su tipo de pregunta elige el texto (contexto_especie.py).
        - Si pregunta algo concreto, se busca el fragmento del Manual.
        - Si menciona una región o vertiente, los registros y su conteo son solo los de esa
          zona; el mapa sigue siendo el nacional.

        Todo se pide con el nombre de la ficha ya validada.
        """
        manual = self._manual(nombre)
        if manual is None:
            return None
        especie = str(manual.valor["species"])
        # Los tipos de bosque del vocabulario también son hábitat.
        intencion = analizar(pregunta, especie, self._vocabulario() if pregunta else None)
        fragmento = _fragmento(especie, pregunta) if intencion.pregunta_especifica else None

        ocurrencias = _ocurrencias(especie)
        avisos: list[str] = []
        if ocurrencias.desactualizado:
            avisos.append(_aviso_registros_anteriores(ocurrencias.actualizado_en))
        mapa = None
        if ocurrencias.sobre is None:
            avisos.append(_aviso_gbif_no_disponible(ocurrencias.intentos))
        elif not alcanza_para_mapa(ocurrencias.total):
            # Con datos insuficientes no se pide el mapa.
            avisos.append(_aviso_pocos_registros(especie, ocurrencias.total))
        else:
            mapa = self._mapa(a_id(especie), especie)
        # La zona se aplica después de decidir el mapa, que usa el total nacional.
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
        """Nombres del catálogo (normalizado -> como lo guarda CR-BioLM), pedidos una sola
        vez.

        search_species sin filtros devuelve todo el catálogo. Si CR-BioLM no responde, no
        se corrige y se vuelven a pedir en la siguiente consulta. También se guarda la
        familia de cada especie, para ofrecer las de un género sin pedir sus fichas.
        """
        if self._nombres_del_catalogo is None:
            try:
                especies = mcp_cliente.llamar("search_species").valor["species"]
                nombres = {normalizar(e["species"]): e["species"] for e in especies}
                familias = {e["species"]: e.get("family") or SIN_DATO for e in especies}
            except (MCPErrorHerramienta, MCPRespuestaInvalida, KeyError, TypeError):
                logger.warning("RR_23: CR-BioLM no dio el catálogo de nombres; no se corrige")
                return {}
            self._familias_del_catalogo = familias
            self._nombres_del_catalogo = nombres
        return self._nombres_del_catalogo

    def _sinonimos(self) -> dict[str, list[EspecieCandidata]]:
        """Sinónimos del catálogo (normalizado -> sus especies), pedidos una sola vez. Si
        CR-BioLM no responde, se vuelven a pedir después.
        """
        if self._sinonimos_del_catalogo is None:
            try:
                filas = mcp_cliente.llamar("list_synonyms").valor
                sinonimos = _sinonimos_por_nombre(filas)
            except (MCPErrorHerramienta, MCPRespuestaInvalida, KeyError, TypeError):
                logger.warning("RR_27: CR-BioLM no dio los sinónimos; no se reconocen")
                return {}
            if not sinonimos:
                return {}
            self._sinonimos_del_catalogo = sinonimos
        return self._sinonimos_del_catalogo

    def _vocabulario(self) -> dict[str, Any] | None:
        """Regiones y vertientes del Manual (get_vocabulary), pedidas una sola vez. Si
        CR-BioLM no responde, no se filtra por zona y se vuelven a pedir después.
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
        """Ficha del Manual, o None si la especie no está en el catálogo. Una ficha de otra
        especie se descarta.
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


# --- nombres comunes (resolve_common_name) -------------------------------------

# Decisiones de resolve_common_name en las que CR-BioLM elige una especie.
_ELIGE_CR_BIOLM = {"unique", "preferred"}


@dataclass(frozen=True)
class _NombreComun:
    """Lo que CR-BioLM dice de un nombre común de la consulta."""

    nombre: str  # como se encontró: el de la consulta o su singular
    decision: str  # "unique", "preferred" o "ambiguous"
    especies: list[dict[str, Any]]  # las candidatas que corresponden


def _por_nombre_comun(
    texto: str, *, ocupadas: list[Frase] | None = None, ya_nombradas: set[str] | None = None
) -> list[EspecieCandidata]:
    """Especies de los nombres comunes de la consulta.

    Las frases se prueban de la más larga a la más corta (nombres_comunes.py); no se prueba
    una que se cruce con un nombre ya reconocido o con `ocupadas`. "unique" o "preferred"
    dan la especie que eligió CR-BioLM; "ambiguous", todas sus candidatas para que el
    usuario elija.

    Un nombre común que nombra a una especie de `ya_nombradas` no agrega nada. Si la frase
    es solo una parte del nombre escrito ("amargo" de "cedro amargo"), sus especies se
    marcan con la frase completa para preguntar antes de responder.
    """
    encontradas: dict[str, EspecieCandidata] = {}
    reconocidas: list[Frase] = list(ocupadas or [])
    for frase in frases_candidatas(texto):
        if any(frase.se_cruza_con(r) for r in reconocidas):
            continue
        try:
            comun = _nombre_comun(frase.texto)
        except (MCPErrorHerramienta, MCPRespuestaInvalida) as error:
            logger.warning("RR_25: CR-BioLM no resolvió nombres comunes: %s", error)
            break
        if comun is None:
            continue
        reconocidas.append(frase)
        if ya_nombradas and any(a_id(c["species"]) in ya_nombradas for c in comun.especies):
            continue
        completa = frase_completa(texto, frase)
        incompleta = completa.texto if completa != frase else None
        for c in comun.especies:
            candidata = EspecieCandidata(
                id=a_id(c["species"]),
                nombre_comun=comun.nombre,
                nombre_cientifico=c["species"],
                familia=c.get("family") or SIN_DATO,
            )
            if incompleta:
                candidata.con_frase_incompleta(incompleta)
            encontradas.setdefault(candidata.id, candidata)
    return list(encontradas.values())


def _nombre_comun(frase: str) -> _NombreComun | None:
    """Especies del catálogo con ese nombre común: primero tal cual y, si no hay ninguna, en
    singular. Los nombres que no se pueden pedir por su id no se ofrecen.
    """
    for variante in (frase, en_singular(frase)):
        if variante is None:
            continue
        valor = mcp_cliente.llamar("resolve_common_name", name=variante).valor
        if not isinstance(valor, dict):
            raise MCPRespuestaInvalida("resolve_common_name", "la respuesta no es un objeto")
        decision = str(valor.get("decision") or "")
        especies = [
            c
            for c in valor.get("candidates") or []
            if isinstance(c, dict)
            and isinstance(c.get("species"), str)
            and a_nombre(a_id(c["species"])) == c["species"]
            and (decision not in _ELIGE_CR_BIOLM or c["species"] == valor.get("species"))
        ]
        if especies:
            return _NombreComun(variante, decision, especies)
    return None


@dataclass(frozen=True)
class _NombreComunUsado:
    """Cómo nombró la consulta a la especie con un nombre común."""

    pregunta: str  # la consulta con el nombre científico al lado
    avisos: list[str]
    nombre_comun: str | None  # el nombre como lo escribió el usuario


def _con_nombre_comun(texto: str, nombre: str) -> _NombreComunUsado:
    """La pregunta con `nombre` junto al nombre común que la nombró, y el aviso.

    "¿Dónde crece la ceiba?" -> "¿Dónde crece la ceiba (Ceiba pentandra)?", para que el
    Manual y el LLM sepan de qué especie se habla. El aviso dice cómo se entendió el nombre
    y de dónde sale la asociación.
    """
    sin_cambios = _NombreComunUsado(texto, [], None)
    if normalizar(nombre) in normalizar(texto):
        return sin_cambios
    for frase in frases_candidatas(texto):
        try:
            comun = _nombre_comun(frase.texto)
        except (MCPErrorHerramienta, MCPRespuestaInvalida):
            return sin_cambios
        especie = (
            next((c for c in comun.especies if c["species"] == nombre), None) if comun else None
        )
        if comun is None or especie is None:
            continue
        pregunta = f"{texto[: frase.fin]} ({nombre}){texto[frase.fin :]}"
        fuentes = especie.get("sources") or []
        avisos = _aviso_de_interpretacion(frase.texto, nombre, comun.decision, fuentes)
        return _NombreComunUsado(pregunta, avisos, _como_nombre(frase.texto))
    return sin_cambios


# De dónde sale que un nombre común es de una especie (los `sources` de
# resolve_common_name), en el orden en que se citan.
_FUENTES_DEL_NOMBRE = {
    "MPCR": "el Manual de Plantas de Costa Rica",
    "INAT_CR": "iNaturalist (Costa Rica)",
    "INAT_ES": "iNaturalist",
    "GBIF": "GBIF",
    "TROPICOS": "Tropicos",
}


def _aviso_de_interpretacion(
    frase: str, nombre: str, decision: str, fuentes: list[str] | None = None
) -> list[str]:
    segun = _segun(fuentes or [])
    if decision == "preferred":
        return [
            f"Por «{frase}» se entendió {nombre}: es el nombre preferido en Costa Rica "
            f"y la especie mejor documentada{segun}."
        ]
    if decision == "unique":
        return [f"Por «{frase}» se entendió {nombre}{segun}."]
    # Ambiguo: el usuario eligió la especie; solo falta decir de dónde sale el nombre.
    return [f"«{frase}» es un nombre común de {nombre}{segun}."] if segun else []


def _segun(fuentes: list[str]) -> str:
    """['MPCR', 'INAT_CR'] -> ' (nombre común según el Manual de Plantas de Costa Rica e
    iNaturalist (Costa Rica))'. Vacío si CR-BioLM no dijo las fuentes."""
    citadas = [nombre for clave, nombre in _FUENTES_DEL_NOMBRE.items() if clave in fuentes]
    if "INAT_CR" in fuentes and "INAT_ES" in fuentes:
        citadas.remove(_FUENTES_DEL_NOMBRE["INAT_ES"])  # iNaturalist una sola vez
    if not citadas:
        return ""
    *primeras, ultima = citadas
    union = "e" if normalizar(ultima).startswith("i") else "y"
    lista = f"{', '.join(primeras)} {union} {ultima}" if primeras else ultima
    return f" (nombre común según {lista})"


def _como_nombre(frase: str) -> str:
    """'olla de mono' u 'OLLA DE MONO' -> 'Olla de mono'."""
    return frase[:1].upper() + frase[1:].lower()


# --- sinónimos científicos (list_synonyms) --------------------------------------


def _sinonimos_por_nombre(filas: Any) -> dict[str, list[EspecieCandidata]]:
    """Filas de list_synonyms agrupadas por sinónimo normalizado, sin los nombres que no se
    pueden pedir por su id.
    """
    if not isinstance(filas, list):
        raise MCPRespuestaInvalida("list_synonyms", "la respuesta no es una lista")
    sinonimos: dict[str, list[EspecieCandidata]] = {}
    for fila in filas:
        if not isinstance(fila, dict) or not all(
            isinstance(fila.get(campo), str) for campo in ("synonym", "species")
        ):
            continue
        especie = fila["species"]
        if a_nombre(a_id(especie)) != especie:
            continue
        candidata = EspecieCandidata(
            id=a_id(especie),
            nombre_comun=None,
            nombre_cientifico=especie,
            familia=fila.get("family") or SIN_DATO,
        )
        sinonimos.setdefault(normalizar(fila["synonym"]), []).append(candidata)
    return sinonimos


def _aviso_de_sinonimo(frase: str, nombre: str) -> str:
    return f"Por «{frase}» se entendió {nombre}: es un sinónimo según GBIF."


def _con_especie_del_genero(texto: str, nombre: str) -> str:
    """'¿Dónde crece Quercus?' -> '¿Dónde crece Quercus costaricensis?'.

    Cuando el usuario eligió la especie de un género, el Manual y el LLM reciben la
    pregunta con ella. Si ya la nombra, o no nombra el género, queda igual.
    """
    if normalizar(nombre) in normalizar(texto):
        return texto
    genero = normalizar(nombre.split()[0])
    for palabra in _PALABRA.finditer(texto):
        if normalizar(palabra.group()) == genero:
            return texto[: palabra.start()] + nombre + texto[palabra.end() :]
    return texto


def _pregunta_de_la_especie(
    texto: str,
    nombre: str,
    nombres: dict[str, str],
    otras: list[tuple[int, int, str]] | None = None,
) -> str:
    """La parte de la pregunta sobre `nombre`, cuando nombra varias especies.

    "¿Dónde crecen Quercus costaricensis en Talamanca y Quercus oleoides en el Valle
    Central?" -> para Quercus oleoides, "¿Dónde crecen Quercus oleoides en el Valle
    Central?". Si solo la última tiene algo después de su nombre, vale para todas. Con una
    sola especie queda igual.

    `otras`: menciones de otras especies por su nombre común, con el formato de
    `_menciones`.
    """
    menciones = sorted([*_menciones(texto, nombres), *(otras or [])])
    if len({canonico for _, _, canonico in menciones}) < 2:
        return texto
    buscada = normalizar(nombre)
    indice = next((i for i, m in enumerate(menciones) if normalizar(m[2]) == buscada), None)
    if indice is None:
        return texto
    tramos = [
        _sin_conectores(texto[fin : siguiente[0]]) for (_, fin, _), siguiente in pairwise(menciones)
    ] + [texto[menciones[-1][1] :]]
    compartido = all(_vacio(t) for t in tramos[:-1]) and not _vacio(tramos[-1])
    inicio, fin, _ = menciones[indice]
    pregunta = texto[: menciones[0][0]] + texto[inicio:fin] + tramos[-1 if compartido else indice]
    if texto.rstrip().endswith("?") and not pregunta.rstrip().endswith("?"):
        pregunta = pregunta.rstrip() + "?"
    return pregunta


def _otras_por_nombre_comun(
    texto: str, nombre: str, nombres: dict[str, str]
) -> list[tuple[int, int, str]]:
    """Otras especies que `texto` nombra por su nombre común. Solo si `nombre` está escrito
    con su nombre científico; un nombre común que también es de `nombre` no cuenta.
    """
    cientificas = _menciones(texto, nombres)
    if not any(normalizar(m[2]) == normalizar(nombre) for m in cientificas):
        return []
    ocupadas = [Frase(texto[i:f], i, f) for i, f, _ in cientificas]
    otras: list[tuple[int, int, str]] = []
    for frase in frases_candidatas(texto):
        if any(frase.se_cruza_con(o) for o in ocupadas):
            continue
        try:
            comun = _nombre_comun(frase.texto)
        except (MCPErrorHerramienta, MCPRespuestaInvalida):
            return []
        if comun is None:
            continue
        ocupadas.append(frase)
        especies = [c["species"] for c in comun.especies]
        if nombre not in especies:
            otras.append((frase.inicio, frase.fin, especies[0]))
    return otras


def _menciones(texto: str, nombres: dict[str, str]) -> list[tuple[int, int, str]]:
    """Dónde nombra `texto` especies del catálogo: (inicio, fin, nombre del catálogo)."""
    menciones: list[tuple[int, int, str]] = []
    for genero, epiteto in pairwise(_PALABRA.finditer(texto)):
        canonico = nombres.get(normalizar(f"{genero.group()} {epiteto.group()}"))
        if canonico and (not menciones or genero.start() >= menciones[-1][1]):
            menciones.append((genero.start(), epiteto.end(), canonico))
    return menciones


# Palabras que unen el tramo de una especie con la siguiente ("… en Talamanca y
# de …"): se quitan del final del tramo.
_CONECTORES_AL_FINAL = re.compile(
    r"(?:[\s,;]+|\b(?:y|e|o|u|ni|de|del|la|el|los|las|a|al|con|vs)\b)+$", re.IGNORECASE
)


def _sin_conectores(tramo: str) -> str:
    return _CONECTORES_AL_FINAL.sub("", tramo)


def _vacio(tramo: str) -> bool:
    """True si el tramo no dice nada además de signos ("?", ", ")."""
    return not re.sub(r"[\s¿?¡!.,;:]", "", tramo)


# --- Manual vectorizado: el fragmento que responde la pregunta ------------------


def _fragmento(especie: str, pregunta: str) -> Fragmento | None:
    """Fragmento del Manual de la especie que mejor responde la pregunta.

    Usa get_relevant_passage de CR-BioLM (búsqueda semántica con embeddings locales, sin
    costo). None si la herramienta falla, si no hay texto vectorizado de la especie o si el
    fragmento es de otra especie; entonces se usa el texto de la ficha. El tiempo agotado
    sí se deja pasar.
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


# --- respuesta redactada por el LLM de CR-BioLM -------------------------------


def _con_redaccion_ia(contexto: ContextoEspecie, pregunta: str) -> ContextoEspecie:
    """El contexto con la respuesta que redacta el LLM, si se pudo obtener. Sin pregunta queda
    el texto del Manual.
    """
    if not pregunta.strip():
        return contexto
    redaccion = _redaccion_ia(contexto.especie, pregunta)
    return replace(contexto, redaccion=redaccion) if redaccion else contexto


def _redaccion_ia(especie: str, pregunta: str) -> RedaccionIA | None:
    """Respuesta de answer_question sobre `especie`, o None para usar el Manual.

    Usa el LLM de CR-BioLM, que necesita OPENROUTER_API_KEY en el .env de CR-BioLM. Es None
    cuando:

    - no queda tiempo en la consulta para esperarlo,
    - la herramienta falla (sin llave, límite del modelo gratuito...),
    - tarda más de SEGUNDOS_MAXIMOS_REDACCION_IA (se descarta sin cortar la consulta),
    - responde sobre otra especie (ver `_validar_redaccion`).
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
    """Tiempo para el LLM sin pasarse del de la consulta; None si no alcanza."""
    segundos = config.SEGUNDOS_MAXIMOS_REDACCION_IA
    restantes = segundos_restantes()
    if restantes is not None:
        segundos = min(segundos, restantes - MARGEN_TRAS_REDACCION)
    return segundos if segundos >= 1 else None


def _validar_redaccion(especie: str, sobre: Sobre) -> RedaccionIA | None:
    """Solo se acepta una respuesta sobre la especie pedida, con citas.

    answer_question decide por su cuenta de qué habla la pregunta, así que se exige que
    haya respondido sobre una especie (modo A) y que todas sus citas sean de la especie que
    identificó el backend.
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


# --- GBIF: reintentos y validación de los registros -----------------------------


def _ocurrencias(especie: str) -> Ocurrencias:
    """Registros de GBIF de la especie, sin los puntos inválidos."""
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
    return Ocurrencias(
        sobre,
        [_registro(p) for p in validos],
        total,
        intentos,
        actualizado_en=_actualizado_en(valor, especie),
        desactualizado=valor.get("stale") is True,
    )


def _actualizado_en(valor: dict[str, Any], especie: str) -> datetime | None:
    """Cuándo descargó CR-BioLM los registros de GBIF ('updated_at', ISO-8601). None si no lo
    indica o no se entiende. Una fecha sin zona horaria se toma como UTC.
    """
    texto = valor.get("updated_at")
    if not isinstance(texto, str) or not texto.strip():
        return None
    try:
        momento = datetime.fromisoformat(texto.strip())
    except ValueError:
        logger.warning("RR_56: fecha de GBIF de %s no válida: %r", especie, texto)
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _en_zona(ocurrencias: Ocurrencias, zona: Zona, especie: str) -> Ocurrencias:
    """Registros válidos de la zona, con su conteo. CR-BioLM entrega a lo sumo 500 puntos por
    defecto; si cortó, se le piden todos para contar bien la zona.
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
    """get_occurrence_points con reintentos: (sobre o None, intentos hechos).

    Se reintenta cuando la herramienta falla dentro de CR-BioLM (GBIF caído, error de red,
    respuesta mal formada). No se reintenta si CR-BioLM está caído ni si se agotó el tiempo
    de la consulta: esos errores suben.
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


def _aviso_registros_anteriores(actualizado_en: datetime | None) -> str:
    """CR-BioLM no pudo actualizar los registros y entregó los anteriores."""
    cuando = f"del {fecha_para_mostrar(actualizado_en)}" if actualizado_en else "anteriores"
    return (
        "No se pudieron actualizar los registros de GBIF en este momento; se muestran "
        f"los {cuando}."
    )


def _aviso_pocos_registros(especie: str, total: int) -> str:
    """Por qué no hay mapa."""
    if total == 0:
        return f"GBIF no tiene registros válidos de {especie} en Costa Rica, así que no hay mapa."
    registros = "1 registro válido" if total == 1 else f"{total} registros válidos"
    return (
        f"Solo hay {registros} de {especie} en Costa Rica y se necesitan al menos "
        f"{config.MINIMO_REGISTROS_MAPA} para generar el mapa, así que no se muestra."
    )


# --- conversión de los datos de CR-BioLM a los esquemas del proyecto ------------


def _pedir_mapa(nombre: str) -> MapaGenerado | None:
    """El mapa de CR-BioLM, o None si no lo genera. Si la herramienta falla, la respuesta sale
    sin mapa; el tiempo agotado sí se deja pasar.
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
    """El mapa recibido es de la especie pedida.

    Se pide con el nombre ya validado; si además CR-BioLM indica otra especie (`species`),
    se descarta. Los guiones bajos se tratan como espacios.
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
    """Un punto de GBIF limpiado por CR-BioLM y validado."""
    return RegistroPresencia(
        localidad=punto.get("region") or SIN_DATO,
        fecha=_fecha(punto),
        latitud=punto["lat"],
        longitud=punto["lon"],
        elevacion_m=punto.get("elev_m"),
        fuente=FUENTE_GBIF,
    )


def _fecha(punto: dict[str, Any]) -> str:
    """Fecha del registro en GBIF ('2019-03-14', '2019-03' o '2019'), o SIN_DATO si no viene."""
    fecha = punto.get("date")
    if not isinstance(fecha, str) or not fecha.strip():
        return SIN_DATO
    return fecha.split("/")[0].split("T")[0].strip()
