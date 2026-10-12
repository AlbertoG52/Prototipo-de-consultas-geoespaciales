/**
 * RR_45 criterio 3: de dónde sale cada dato de una respuesta o de una ficha
 * (campo `procedencia`).
 *
 * Plegado por defecto para no recargar la tarjeta. Presentación mínima; el
 * diseño final de la respuesta es de quien lleva TarjetaRespuesta.
 */
import { ETIQUETAS_DATO } from "../config/textos";
import type { Procedencia } from "../types";

export function OrigenDeLosDatos({ procedencia, className = "" }: { procedencia: Procedencia[]; className?: string }) {
  if (procedencia.length === 0) return null;
  return (
    <details className={`text-xs ${className}`} style={{ color: "var(--color-texto-secundario)" }}>
      <summary className="cursor-pointer select-none" style={{ color: "var(--color-texto-tenue)" }}>
        Origen de los datos
      </summary>
      <ul className="mt-2 flex flex-col gap-1">
        {procedencia.map((p) => (
          <li key={p.dato}>
            <span className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>
              {ETIQUETAS_DATO[p.dato]}:
            </span>{" "}
            {p.fuente} — {p.detalle}
          </li>
        ))}
      </ul>
    </details>
  );
}
