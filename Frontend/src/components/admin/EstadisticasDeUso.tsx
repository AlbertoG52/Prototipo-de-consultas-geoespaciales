/**
 * RR_78 — estadísticas de uso del sistema (GET /admin/estadisticas).
 *
 * Criterio 1: el total de consultas del periodo elegido. Criterio 2: por rol
 * (el que cada cuenta tiene hoy) y visitantes. Criterio 3: se recarga sola cada
 * 30 s mientras esta sección y la pestaña del navegador están a la vista, sin
 * mostrar "Cargando…" ni perder el periodo elegido; también con "Actualizar".
 * Incluye las consultas por día (últimos 7) y por tipo de pregunta (RR_29).
 */
import { useCallback, useRef, useState } from "react";

import { RefreshCw } from "lucide-react";
import {
  ETIQUETAS_GRUPO_DE_USO,
  ETIQUETAS_PERIODO,
  ETIQUETAS_TIPO_PREGUNTA,
  IDIOMA_FECHAS,
  formatearNumero,
  formatearPorcentaje,
} from "../../config/textos";
import { useRecargaAutomatica } from "../../hooks/useRecargaAutomatica";
import * as api from "../../services/api";
import type { EstadisticasUso, GrupoDeUso, PeriodoEstadisticas, TipoPregunta } from "../../types";

const RECARGA_MS = 30_000; // RR_78 criterio 3

const PERIODOS = Object.keys(ETIQUETAS_PERIODO) as PeriodoEstadisticas[];

const COLOR_GRUPO: Record<GrupoDeUso, string> = {
  visitante: "var(--color-grafico-4)",
  usuario: "var(--color-grafico-3)",
  moderador: "var(--color-grafico-2)",
  supermoderador: "var(--color-grafico-1)",
};

const COLOR_TIPO: Record<TipoPregunta, string> = {
  distribucion: "var(--color-grafico-2)",
  habitat: "var(--color-grafico-3)",
  descripcion: "var(--color-grafico-4)",
  general: "var(--color-grafico-5)",
};

const TARJETA = { background: "var(--color-superficie)", border: "1px solid var(--color-borde)" };

const parte = (n: number, total: number) => (total ? n / total : 0);

/** "2026-10-22" (día en UTC) → "jue 22". */
function nombreDelDia(fecha: string) {
  const dia = new Date(`${fecha}T00:00:00Z`);
  return dia.toLocaleDateString(IDIOMA_FECHAS, { weekday: "short", day: "numeric", timeZone: "UTC" });
}

export function EstadisticasDeUso() {
  const [periodo, setPeriodo] = useState<PeriodoEstadisticas>("todo");
  const [datos, setDatos] = useState<EstadisticasUso | null>(null);
  const [error, setError] = useState<string | null>(null);
  // La respuesta de un periodo anterior que llegue tarde no debe pisar la actual.
  const periodoVigente = useRef(periodo);

  const cargar = useCallback(() => {
    periodoVigente.current = periodo;
    api
      .obtenerEstadisticas(periodo)
      .then((d) => {
        if (d.periodo !== periodoVigente.current) return;
        setDatos(d);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "No se pudieron cargar las estadísticas."));
  }, [periodo]);
  useRecargaAutomatica(cargar, RECARGA_MS);

  return (
    <section aria-label="Estadísticas de uso" className="flex flex-col gap-4">
      <div className="rounded-2xl p-6" style={TARJETA}>
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="font-semibold" style={{ color: "var(--color-texto)" }}>Estadísticas de uso</h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
              Se actualizan solas cada 30 segundos mientras ves esta sección.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {datos && (
              <span role="status" className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>
                Actualizado a las {new Date(datos.generado_en).toLocaleTimeString(IDIOMA_FECHAS)}
              </span>
            )}
            <button
              type="button"
              onClick={cargar}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
              style={{ background: "transparent", color: "var(--color-texto-secundario)", border: "1px solid var(--color-borde)", cursor: "pointer" }}
            >
              <RefreshCw size={12} aria-hidden /> Actualizar
            </button>
          </div>
        </div>

        <SelectorDePeriodo periodo={periodo} alCambiar={setPeriodo} />

        {error && (
          <div role="alert" className="rounded-xl px-4 py-3 mt-4 text-sm" style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", color: "var(--color-error-texto)" }}>
            {error}
          </div>
        )}

        {datos ? <Totales datos={datos} /> : !error && <p className="text-sm mt-4" style={{ color: "var(--color-texto-tenue)" }}>Cargando…</p>}
      </div>

      {datos && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PorDia datos={datos} />
          <PorTipo datos={datos} />
        </div>
      )}
    </section>
  );
}

function SelectorDePeriodo({ periodo, alCambiar }: { periodo: PeriodoEstadisticas; alCambiar: (p: PeriodoEstadisticas) => void }) {
  return (
    <div role="group" aria-label="Periodo" className="flex flex-wrap gap-2">
      {PERIODOS.map((p) => (
        <button
          key={p}
          type="button"
          aria-pressed={p === periodo}
          onClick={() => alCambiar(p)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium"
          style={{
            background: p === periodo ? "var(--color-marca)" : "var(--color-superficie-suave)",
            color: p === periodo ? "var(--color-sobre-marca)" : "var(--color-texto-cuerpo)",
            border: "none",
            cursor: "pointer",
          }}
        >
          {ETIQUETAS_PERIODO[p]}
        </button>
      ))}
    </div>
  );
}

/** Criterios 1 y 2: el total del periodo y cuánto aportó cada grupo. */
function Totales({ datos }: { datos: EstadisticasUso }) {
  return (
    <>
      <div className="mt-5 mb-5">
        <div className="text-3xl font-bold" style={{ color: "var(--color-texto)" }}>
          {formatearNumero(datos.total)} {datos.total === 1 ? "consulta" : "consultas"}
        </div>
        <div className="text-xs mt-1" style={{ color: "var(--color-texto-secundario)" }}>
          {formatearNumero(datos.resueltas)} resueltas
          {datos.tasa_exito !== null && ` · tasa de éxito ${formatearPorcentaje(datos.tasa_exito)}`}
        </div>
      </div>
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--color-texto)" }}>Por rol</h3>
      {datos.por_grupo.map((g) => (
        <div key={g.grupo} className="mb-3">
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>{ETIQUETAS_GRUPO_DE_USO[g.grupo]}</span>
            <span style={{ color: "var(--color-texto-secundario)" }}>
              {formatearNumero(g.consultas)} · {formatearPorcentaje(parte(g.consultas, datos.total))}
            </span>
          </div>
          <div className="rounded-full overflow-hidden" style={{ height: 8, background: "var(--color-superficie-suave)" }}>
            <div className="h-full rounded-full" style={{ width: `${parte(g.consultas, datos.total) * 100}%`, background: COLOR_GRUPO[g.grupo], transition: "width 0.6s" }} />
          </div>
        </div>
      ))}
      <p className="text-xs mt-4" style={{ color: "var(--color-texto-tenue)" }}>
        Cuentan las consultas resueltas, ambiguas y sin coincidencias; no los saludos ni la ayuda. Cada cuenta
        cuenta con el rol que tiene hoy. De los visitantes, una consulta ambigua cuenta cuando elige la especie.
      </p>
    </>
  );
}

function PorDia({ datos }: { datos: EstadisticasUso }) {
  const maximo = Math.max(1, ...datos.por_dia.map((d) => d.consultas));
  const ultimo = datos.por_dia.length - 1;
  return (
    <div className="rounded-2xl p-6" style={TARJETA}>
      <h3 className="font-semibold mb-4 text-sm" style={{ color: "var(--color-texto)" }}>Consultas por día (últimos 7 días)</h3>
      <div className="flex items-end gap-2" style={{ height: 80 }}>
        {datos.por_dia.map((d, i) => (
          <div
            key={d.fecha}
            className="flex-1 rounded-t-md transition-all"
            style={{ height: `${Math.max(parte(d.consultas, maximo) * 100, 2)}%`, background: i === ultimo ? "var(--color-marca)" : "var(--color-borde-fuerte)" }}
            title={`${nombreDelDia(d.fecha)}: ${formatearNumero(d.consultas)}`}
          />
        ))}
      </div>
      <div className="flex justify-between gap-2 text-xs mt-2" style={{ color: "var(--color-texto-tenue)" }}>
        {datos.por_dia.map((d) => (
          <span key={d.fecha} className="flex-1 text-center">{nombreDelDia(d.fecha)}</span>
        ))}
      </div>
    </div>
  );
}

function PorTipo({ datos }: { datos: EstadisticasUso }) {
  const total = datos.por_tipo.reduce((suma, t) => suma + t.consultas, 0);
  return (
    <div className="rounded-2xl p-6" style={TARJETA}>
      <h3 className="font-semibold mb-4 text-sm" style={{ color: "var(--color-texto)" }}>Tipos de consulta</h3>
      {datos.por_tipo.map((t) => (
        <div key={t.tipo} className="flex items-center gap-2 mb-2 text-xs">
          <div className="rounded-sm shrink-0" style={{ width: 10, height: 10, background: COLOR_TIPO[t.tipo] }} />
          <span style={{ color: "var(--color-texto-cuerpo)", flex: 1 }}>{ETIQUETAS_TIPO_PREGUNTA[t.tipo]}</span>
          <span style={{ color: "var(--color-texto-secundario)" }}>{formatearNumero(t.consultas)}</span>
          <span className="font-medium text-right" style={{ color: "var(--color-texto)", minWidth: 48 }}>
            {formatearPorcentaje(parte(t.consultas, total))}
          </span>
        </div>
      ))}
      <p className="text-xs mt-3" style={{ color: "var(--color-texto-tenue)" }}>
        Según el tipo de pregunta detectado en cada consulta resuelta o sin coincidencias.
      </p>
    </div>
  );
}
