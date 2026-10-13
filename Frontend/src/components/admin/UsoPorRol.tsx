/**
 * RR_76 criterio 3 — uso del sistema por rol (GET /admin/uso-por-rol).
 *
 * Cuántas cuentas tiene cada rol y cuántas consultas guardadas hicieron, según
 * el rol que cada cuenta tiene hoy. El detalle por cuenta está en "Ver uso".
 */
import { ETIQUETAS_ROL, formatearNumero } from "../../config/textos";
import type { UsoDeRol } from "../../types";

const plural = (n: number, singular: string, plural: string) =>
  `${formatearNumero(n)} ${n === 1 ? singular : plural}`;

export function UsoPorRol({ uso }: { uso: UsoDeRol[] }) {
  return (
    <section aria-label="Uso del sistema por rol" className="rounded-2xl px-6 py-4 mb-4" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
      <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--color-texto)" }}>Uso por rol</h2>
      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {uso.map((u) => (
          <div key={u.rol} className="rounded-xl px-3 py-2" style={{ background: "var(--color-superficie-suave)" }}>
            <dt className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>{ETIQUETAS_ROL[u.rol]}</dt>
            <dd className="text-sm font-semibold mt-0.5" style={{ color: "var(--color-texto)" }}>
              {plural(u.consultas, "consulta", "consultas")}
              <span className="text-xs font-normal" style={{ color: "var(--color-texto-secundario)" }}>
                {" · "}{plural(u.usuarios, "cuenta", "cuentas")}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
