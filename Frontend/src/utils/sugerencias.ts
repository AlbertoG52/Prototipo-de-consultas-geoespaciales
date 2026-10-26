/**
 * RR_16 — cómo se incorpora una sugerencia de especie al campo de consulta.
 */
import type { EspecieCandidata } from "../types";

/** Minúsculas y sin tildes, igual que la comparación del servidor. */
export const normalizar = (s: string) => s.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");

/** Última palabra que se está escribiendo (letras y guiones al final del texto). */
export const palabraEnCurso = (texto: string) => texto.match(/[\p{L}\p{M}-]+$/u)?.[0] ?? "";

/**
 * Reemplaza por `nombre` el final del texto que ya coincide con su comienzo,
 * para que "guaria mo" pase a "Guaria morada" y no a "guaria Guaria morada".
 * Si ningún final coincide, reemplaza solo la palabra en curso.
 */
export function incorporarNombre(texto: string, nombre: string): string {
  const objetivo = normalizar(nombre);
  let inicio = texto.length - palabraEnCurso(texto).length;
  for (let i = 0; i < inicio; i++) {
    if ((i === 0 || /\s/.test(texto[i - 1])) && objetivo.startsWith(normalizar(texto.slice(i)))) {
      inicio = i;
      break;
    }
  }
  return `${texto.slice(0, inicio)}${nombre} `;
}

/** Se inserta el nombre común, o el científico si fue ese el que se escribió. */
export function nombreAInsertar(especie: EspecieCandidata, fragmento: string): string {
  const comun = especie.nombre_comun;
  const buscado = normalizar(fragmento);
  const enComun = comun && normalizar(comun).split(/\s+/).some((p) => p.startsWith(buscado));
  return enComun ? comun : especie.nombre_cientifico;
}
