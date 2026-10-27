/**
 * RR_36 — cuándo una consulta ambigua nombra varias especies distintas.
 *
 * El servidor responde "ambigua" (RR_17) tanto si la consulta nombra varias
 * especies ("Quercus costaricensis y Quercus oleoides") como si nombra solo un
 * género ("Quercus", RR_28). Son varias especies nombradas cuando cada opción
 * está escrita en la consulta, sin importar mayúsculas ni tildes: entonces se
 * ofrece buscarlas todas.
 */
import { normalizar } from "./sugerencias";

/** El mensaje de las opciones cuando se pueden buscar todas. */
export const MENSAJE_VARIAS_ESPECIES = "Tu consulta menciona varias especies. Elige una o búscalas todas.";

/** ' Quercus  costaricensis? ' -> ' quercus costaricensis ': para buscar un nombre entero. */
const palabras = (s: string) => ` ${normalizar(s).replace(/[^\p{L}\p{N}]+/gu, " ").trim()} `;

export function nombraVariasEspecies(texto: string, candidatos: { nombre_cientifico: string }[]): boolean {
  const consulta = palabras(texto);
  return candidatos.length > 1 && candidatos.every((c) => consulta.includes(palabras(c.nombre_cientifico)));
}

/** Por qué no se buscan todas: cada especie consume una consulta. */
export function consultasInsuficientes(necesarias: number, restantes: number): string {
  const quedan = restantes === 1 ? "te queda 1" : `te quedan ${restantes}`;
  return `Consultas insuficientes: para buscarlas todas necesitas ${necesarias} y ${quedan}.`;
}
