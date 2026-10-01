/**
 * Mapa provisional de distribución y sus controles — RR_06, RR_12, RR_18 y RR_19.
 */
import { useEffect, type Ref } from "react";

import type { RegistroPresencia } from "../types";
import { RANGO_VACIO, type RangoElevacion } from "../utils/elevacion";

/**
 * Mapa de distribución.
 *
 * El mapa geoespacial real lo genera CR-BioLM y es parte del módulo 3, que no
 * pertenece a este sprint. Esto dibuja los registros que sí tenemos sobre una
 * silueta del país, proyectando latitud y longitud a coordenadas del SVG, para
 * que la alternancia de RR_18 tenga las dos vistas que compara.
 *
 * - `indices` son los registros visibles; el filtro de RR_19 puede ocultar algunos.
 * - `seleccionado` es el índice del punto cuyo detalle está abierto (RR_12).
 * - `ref` expone el elemento SVG para poder descargarlo (RR_15).
 */
export function MapaDistribucion({
  registros,
  indices,
  seleccionado,
  onSeleccionar,
  ref,
}: {
  registros: RegistroPresencia[];
  indices: number[];
  seleccionado: number | null;
  onSeleccionar: (indice: number | null) => void;
  ref?: Ref<SVGSVGElement>;
}) {
  // Recuadro aproximado de Costa Rica.
  const LON_MIN = -86.0;
  const LON_MAX = -82.5;
  const LAT_MIN = 8.0;
  const LAT_MAX = 11.3;

  const aX = (lon: number) => 60 + ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * 220;
  const aY = (lat: number) => 150 - ((lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * 100;

  // El punto seleccionado se dibuja al final para que quede encima de los demás.
  const orden = indices.filter((i) => i !== seleccionado);
  if (seleccionado !== null && indices.includes(seleccionado)) orden.push(seleccionado);

  return (
    <svg
      ref={ref}
      viewBox="0 0 340 180"
      className="w-full h-full"
      style={{ background: "#e8f0e8" }}
      role="group"
      aria-label="Mapa de distribución en Costa Rica"
      // RR_12 criterio 3: un clic fuera de los puntos cierra el detalle.
      onClick={() => onSeleccionar(null)}
    >
      <path
        d="M60,90 Q80,60 120,55 Q160,50 200,60 Q230,65 250,80 Q270,90 260,110 Q250,130 220,140 Q180,150 140,148 Q100,145 75,130 Q50,115 60,90 Z"
        fill="#c8dfc0"
        stroke="#9ab89a"
        strokeWidth="1.5"
      />
      {orden.map((i) => {
        const r = registros[i];
        const activo = i === seleccionado;
        const alternar = () => onSeleccionar(activo ? null : i);
        return (
          <circle
            key={i}
            cx={aX(r.longitud)}
            cy={aY(r.latitud)}
            r={activo ? 7 : 4.5}
            fill={activo ? "#e0552b" : "#5b4fcf"}
            stroke={activo ? "#ffffff" : "none"}
            strokeWidth={activo ? 2 : 0}
            opacity={activo ? 1 : 0.85}
            role="button"
            tabIndex={0}
            aria-pressed={activo}
            aria-label={`Registro en ${r.localidad}, ${r.fecha}. Ver detalle.`}
            style={{ cursor: "pointer" }}
            // RR_12 criterio 1: al seleccionar un punto se abre su detalle.
            onClick={(e) => {
              e.stopPropagation();
              alternar();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                alternar();
              }
            }}
          >
            <title>{`${r.localidad} — ${r.fecha}`}</title>
          </circle>
        );
      })}
      <circle cx="100" cy="160" r="5" fill="#5b4fcf" opacity="0.85" />
      <text x="110" y="164" fontSize="9" fill="#555" fontFamily="Inter, sans-serif">
        Registros de presencia ({indices.length})
      </text>
      <line x1="240" y1="162" x2="290" y2="162" stroke="#666" strokeWidth="1.5" />
      <line x1="240" y1="158" x2="240" y2="162" stroke="#666" strokeWidth="1.5" />
      <line x1="290" y1="158" x2="290" y2="162" stroke="#666" strokeWidth="1.5" />
      <text x="257" y="172" fontSize="8" fill="#666" fontFamily="Inter, sans-serif">
        50 km
      </text>
    </svg>
  );
}

/**
 * RR_12 — detalle del punto seleccionado.
 *
 * Va debajo del mapa (HTML, no dentro del SVG) para que no lo tape ni salga en
 * la descarga del mapa (RR_15). Se cierra con la X, con Escape, con un clic en
 * el fondo del mapa o volviendo a hacer clic en el mismo punto.
 */
export function DetallePunto({ registro, onCerrar }: { registro: RegistroPresencia; onCerrar: () => void }) {
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCerrar();
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  const filas: [string, string][] = [
    ["Localidad", registro.localidad],
    ["Fecha del registro", registro.fecha],
    ["Coordenadas", `${registro.latitud.toFixed(4)}, ${registro.longitud.toFixed(4)}`],
    ["Elevación", registro.elevacion_m !== null ? `${registro.elevacion_m} msnm` : "Sin dato"],
    ["Fuente", registro.fuente],
  ];

  return (
    <div
      role="region"
      aria-live="polite"
      aria-label={`Detalle del registro en ${registro.localidad}`}
      className="mt-2 rounded-xl px-4 py-3 text-xs"
      style={{ background: "#f7faf7", border: "1px solid #c5dccb" }}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="flex items-center gap-1.5 font-semibold" style={{ color: "#1e3d2a" }}>
          <span className="inline-block rounded-full" style={{ width: 8, height: 8, background: "#e0552b" }} />
          Detalle del registro
        </span>
        <button
          onClick={onCerrar}
          aria-label="Cerrar detalle"
          className="flex items-center gap-1 px-2 py-1 rounded-md"
          style={{ border: "none", background: "transparent", color: "#6b8f74", cursor: "pointer" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          Cerrar
        </button>
      </div>
      <dl className="grid gap-x-4 gap-y-1" style={{ gridTemplateColumns: "auto 1fr" }}>
        {filas.map(([k, v]) => (
          <div key={k} className="contents">
            <dt style={{ color: "#8aab92" }}>{k}</dt>
            <dd className="font-medium" style={{ color: "#374a3c" }}>
              {v}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** RR_19 — campos para definir el rango de elevación y quitar el filtro. */
export function FiltroElevacion({
  rango,
  onCambiar,
  visibles,
  total,
  activo,
  error,
}: {
  rango: RangoElevacion;
  onCambiar: (rango: RangoElevacion) => void;
  visibles: number;
  total: number;
  activo: boolean;
  error: string | null;
}) {
  const hayTexto = rango.min !== "" || rango.max !== "";
  const estiloCampo = {
    width: 84,
    border: `1.5px solid ${error ? "#fca5a5" : "#c5dccb"}`,
    background: "#f7f8f5",
    color: "#1e3d2a",
  };

  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 flex-wrap text-xs" role="group" aria-label="Filtrar por elevación">
        <span className="font-medium" style={{ color: "#374a3c" }}>
          Elevación (msnm):
        </span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          placeholder="Mínima"
          aria-label="Elevación mínima en metros"
          value={rango.min}
          onChange={(e) => onCambiar({ ...rango, min: e.target.value })}
          className="rounded-lg px-2 py-1 outline-none"
          style={estiloCampo}
        />
        <span style={{ color: "#8aab92" }}>a</span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          placeholder="Máxima"
          aria-label="Elevación máxima en metros"
          value={rango.max}
          onChange={(e) => onCambiar({ ...rango, max: e.target.value })}
          className="rounded-lg px-2 py-1 outline-none"
          style={estiloCampo}
        />
        {/* RR_19 criterio 3: volver a ver todos los puntos. */}
        {hayTexto && (
          <button
            onClick={() => onCambiar(RANGO_VACIO)}
            className="px-2 py-1 rounded-lg font-medium"
            style={{ border: "1px solid #c5dccb", background: "transparent", color: "#2d5a3d", cursor: "pointer" }}
          >
            Quitar filtro
          </button>
        )}
        {activo && (
          <span aria-live="polite" style={{ color: "#6b8f74" }}>
            Mostrando {visibles} de {total} registros
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className="text-xs mt-1" style={{ color: "#991b1b" }}>
          {error}
        </p>
      )}
    </div>
  );
}
