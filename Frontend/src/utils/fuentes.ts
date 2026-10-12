/**
 * RR_50 y RR_51 — de qué fuente sale cada parte de una respuesta.
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
