/**
 * RR_36 — cuándo una consulta ambigua nombra varias especies distintas.
 *
 * El servidor responde "ambigua" (RR_17) tanto si la consulta nombra varias
 * especies ("Quercus costaricensis y Quercus oleoides") como si nombra solo un
 * género ("Quercus", RR_28). Son varias especies nombradas cuando cada opción
 * está escrita en la consulta, por su nombre científico o común, sin importar
 * mayúsculas ni tildes, y hay al menos dos nombres distintos ("el cocobolo y
 * Quercus oleoides", DEF-07): entonces se ofrece buscarlas todas. Un solo
 * nombre común de varias especies ("cocobolo") es para elegir una.
 */
import { normalizar } from "./sugerencias";

/** El mensaje de las opciones cuando se pueden buscar todas. */
export const MENSAJE_VARIAS_ESPECIES = "Tu consulta menciona varias especies. Elige una o búscalas todas.";

/** ' Quercus  costaricensis? ' -> ' quercus costaricensis ': para buscar un nombre entero. */
const palabras = (s: string) => ` ${normalizar(s).replace(/[^\p{L}\p{N}]+/gu, " ").trim()} `;

/** DEF-14: el servidor no encontró el nombre completo, solo un pedazo de él. */
export const PREFIJO_NOMBRE_INCOMPLETO = "No encontré «";

export function nombraVariasEspecies(
  texto: string,
  candidatos: { nombre_cientifico: string; nombre_comun: string | null }[],
  mensaje?: string | null,
): boolean {
  // "cedro amargo" no es "cedro" y "amargo": son pedazos de un nombre que no está.
  if (mensaje?.startsWith(PREFIJO_NOMBRE_INCOMPLETO)) return false;
  const consulta = palabras(texto);
  const escritos = candidatos.map((c) =>
    [c.nombre_cientifico, c.nombre_comun].find((n) => n && consulta.includes(palabras(n))),
  );
  if (candidatos.length < 2 || !escritos.every(Boolean)) return false;
  return new Set(escritos.map((n) => palabras(n!))).size > 1;
}

/** Por qué no se buscan todas: cada especie consume una consulta. */
export function consultasInsuficientes(necesarias: number, restantes: number): string {
  const quedan = restantes === 1 ? "te queda 1" : `te quedan ${restantes}`;
  return `Consultas insuficientes: para buscarlas todas necesitas ${necesarias} y ${quedan}.`;
}
