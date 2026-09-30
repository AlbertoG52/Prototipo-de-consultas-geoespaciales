/**
 * RR_19 — filtrado de los registros por rango de elevación.
 *
 * Los límites llegan como texto desde los campos del formulario: "" significa
 * que ese extremo no se definió. Se valida aquí para que la vista solo tenga
 * que mostrar el resultado.
 */
import type { RegistroPresencia } from "../types";

export interface RangoElevacion {
  min: string;
  max: string;
}

export const RANGO_VACIO: RangoElevacion = { min: "", max: "" };

export interface ResultadoFiltro {
  /** Índices (en el arreglo original) de los registros que quedan visibles. */
  indices: number[];
  /** true si el usuario definió al menos un extremo válido. */
  activo: boolean;
  /** Motivo por el que el rango no se aplicó, si es inválido. */
  error: string | null;
}

function aNumero(texto: string): number | null | "invalido" {
  const t = texto.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : "invalido";
}

export function filtrarPorElevacion(
  registros: RegistroPresencia[],
  rango: RangoElevacion,
): ResultadoFiltro {
  const todos = registros.map((_, i) => i);
  const min = aNumero(rango.min);
  const max = aNumero(rango.max);

  if (min === "invalido" || max === "invalido") {
    return { indices: todos, activo: false, error: "Escribe la elevación en metros, solo con números." };
  }
  if (min === null && max === null) {
    return { indices: todos, activo: false, error: null };
  }
  if (min !== null && max !== null && min > max) {
    return { indices: todos, activo: false, error: "La elevación mínima no puede ser mayor que la máxima." };
  }

  // Un registro sin elevación no se puede ubicar en el rango, así que queda fuera.
  const indices = todos.filter((i) => {
    const e = registros[i].elevacion_m;
    if (e === null) return false;
    return (min === null || e >= min) && (max === null || e <= max);
  });
  return { indices, activo: true, error: null };
}
