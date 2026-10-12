/**
 * Avisos sobre los datos de una respuesta o de una ficha (campo `avisos`).
 *
 * El backend los agrega cuando la respuesta sale incompleta y el usuario debe
 * saberlo, p. ej.:
 *  - RR_43: no hay registros suficientes para generar el mapa.
 *  - RR_58: no se pudo consultar GBIF después de los reintentos.
 *
 * Presentación mínima; el diseño final de la respuesta es de quien lleva
 * TarjetaRespuesta y Mapa.
 */
import { TriangleAlert } from "lucide-react";

export function Avisos({ avisos, className = "" }: { avisos: string[]; className?: string }) {
  if (avisos.length === 0) return null;
  return (
    <ul role="status" className={`flex flex-col gap-2 ${className}`}>
      {avisos.map((aviso) => (
        <li
          key={aviso}
          className="flex items-start gap-2 text-sm rounded-xl px-3 py-2"
          style={{
            background: "var(--color-aviso-fondo)",
            border: "1px solid var(--color-aviso-borde)",
            color: "var(--color-aviso-texto)",
          }}
        >
          <TriangleAlert size={16} className="shrink-0 mt-0.5" style={{ color: "var(--color-aviso)" }} aria-hidden="true" />
          <span>{aviso}</span>
        </li>
      ))}
    </ul>
  );
}
