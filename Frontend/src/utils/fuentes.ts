/**
 * RR_49, RR_50 y RR_51 — de qué fuente sale cada parte de una respuesta.
 *
 * Todo sale del campo `procedencia` que arma el backend (RR_45,
 * services/contexto_especie.py): aquí solo se elige qué mostrar.
 */
import { FUENTE_GBIF, FUENTE_MANUAL } from "../config/textos";
import type { DatoRespuesta, Procedencia } from "../types";

/** La procedencia de un dato de la respuesta (texto, registros…), si la trae. */
export function procedenciaDe(procedencia: Procedencia[], dato: DatoRespuesta): Procedencia | undefined {
  return procedencia.find((p) => p.dato === dato);
}

/**
 * RR_51 criterio 1: si la información viene del Manual de Plantas (MPCR), de
 * GBIF o de ambas. null si la respuesta no trae procedencia.
 */
export function origenDeLaInformacion(procedencia: Procedencia[]): string | null {
  const fuentes = new Set(procedencia.map((p) => p.fuente));
  const manual = fuentes.has(FUENTE_MANUAL);
  const gbif = fuentes.has(FUENTE_GBIF);
  if (manual && gbif) return `${FUENTE_MANUAL} (MPCR) y ${FUENTE_GBIF}`;
  if (manual) return `${FUENTE_MANUAL} (MPCR)`;
  if (gbif) return FUENTE_GBIF;
  return null;
}

/** Un trozo del texto de la respuesta: texto corrido o una cita del Manual. */
export type TrozoDeTexto =
  | { tipo: "texto"; valor: string }
  | { tipo: "cita"; valor: string; completa: string };

/**
 * RR_49 y RR_51 — el texto que redacta el LLM de CR-BioLM trae las citas del
 * Manual dentro, entre 【 】: "…en Talamanca【Quercus costaricensis (Tomo V, p.779)】."
 * Se separan para mostrarlas como cita ("Tomo V, p.779"); `completa` conserva la
 * cita entera. Un texto sin citas (el del Manual) queda en un solo trozo.
 */
export function partirCitas(texto: string): TrozoDeTexto[] {
  const trozos: TrozoDeTexto[] = [];
  let desde = 0;
  for (const cita of texto.matchAll(/【([^】]*)】/g)) {
    const inicio = cita.index ?? 0;
    if (inicio > desde) trozos.push({ tipo: "texto", valor: texto.slice(desde, inicio) });
    const completa = cita[1].trim();
    const ubicacion = /\(([^()]+)\)\s*$/.exec(completa);
    trozos.push({ tipo: "cita", valor: ubicacion ? ubicacion[1].trim() : completa, completa });
    desde = inicio + cita[0].length;
  }
  if (desde < texto.length) trozos.push({ tipo: "texto", valor: texto.slice(desde) });
  return trozos;
}

/** Un trozo de texto con su formato. */
export type TrozoConFormato = { valor: string; negrita: boolean; cursiva: boolean };

/**
 * RR_49 — el texto que redacta el LLM de CR-BioLM viene en Markdown: "**bosques
 * nubosos**" es negrita y "*Quercus*" cursiva. Se separan para mostrarlos con ese
 * formato y sin los asteriscos. Un texto sin marcas queda en un solo trozo.
 */
export function partirFormato(texto: string): TrozoConFormato[] {
  const trozos: TrozoConFormato[] = [];
  let desde = 0;
  for (const marca of texto.matchAll(/\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*/g)) {
    const inicio = marca.index ?? 0;
    if (inicio > desde) trozos.push({ valor: texto.slice(desde, inicio), negrita: false, cursiva: false });
    const negrita = marca[1] !== undefined;
    trozos.push({ valor: negrita ? marca[1] : marca[2], negrita, cursiva: !negrita });
    desde = inicio + marca[0].length;
  }
  if (desde < texto.length) trozos.push({ valor: texto.slice(desde), negrita: false, cursiva: false });
  return trozos;
}
