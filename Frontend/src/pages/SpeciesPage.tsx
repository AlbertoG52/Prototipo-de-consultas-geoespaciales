/**
 * Ficha completa de la especie — RR_20.
 *
 *  - Criterio 1: muestra los datos disponibles de la especie (nombre, familia,
 *    hábitat, elevación), además de la descripción y sus registros.
 *  - Criterio 2: los datos se piden al backend con el id de la URL
 *    (/species/:name), así que corresponden a la especie consultada. Antes la
 *    ficha mostraba siempre la guaria morada con datos fijos.
 *  - Criterio 3: se llega desde el botón "Ficha completa" de cada respuesta
 *    (ChatPage).
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import * as api from "../services/api";
import type { FichaEspecie } from "../types";
import { descargarArchivo, fichaATexto } from "../utils/descarga";

type Estado =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; ficha: FichaEspecie };

const SIN_DATO = "Sin dato";

export function SpeciesPage() {
  const { name } = useParams();
  const navigate = useNavigate();
  const especieId = name ? decodeURIComponent(name) : "";
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando" });

  useEffect(() => {
    if (!especieId) {
      setEstado({ tipo: "error", mensaje: "No se indicó ninguna especie." });
      return;
    }
    // Si se cambia de especie antes de que llegue la respuesta anterior, esa
    // respuesta se descarta para no mostrar la ficha equivocada.
    let vigente = true;
    setEstado({ tipo: "cargando" });
    api
      .obtenerFicha(especieId)
      .then((ficha) => vigente && setEstado({ tipo: "lista", ficha }))
      .catch((err) => {
        if (!vigente) return;
        const mensaje =
          err instanceof api.ErrorApi && err.status === 404
            ? "No se encontró información de esa especie."
            : err instanceof Error
              ? err.message
              : "No se pudo cargar la ficha.";
        setEstado({ tipo: "error", mensaje });
      });
    return () => {
      vigente = false;
    };
  }, [especieId]);

  const exportar = (ficha: FichaEspecie) =>
    descargarArchivo(`florabot-ficha-${ficha.id}.txt`, fichaATexto(ficha), "text/plain;charset=utf-8");

  return (
    <>
      {/* Encabezado */}
      <div
        className="px-8 py-4 border-b shrink-0 flex items-center gap-3"
        style={{ background: "#ffffff", borderColor: "#dde8df" }}
      >
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm transition-all rounded-lg px-3 py-2"
          style={{ color: "#6b8f74", border: "none", background: "transparent", cursor: "pointer" }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "#f0f5f1";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M19 12H5M12 5l-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Volver a consultas
        </button>
        <span style={{ color: "#dde8df" }}>|</span>
        <h1 className="text-base font-medium" style={{ color: "#1e3d2a" }}>
          Ficha completa de especie
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ background: "#f7f8f5" }}>
        {estado.tipo === "cargando" && (
          <div className="px-8 py-10 text-sm" role="status" style={{ color: "#6b8f74" }}>
            Cargando la ficha…
          </div>
        )}

        {estado.tipo === "error" && (
          <div className="px-8 py-10 max-w-xl">
            <div
              role="alert"
              className="rounded-xl p-4 text-sm"
              style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b" }}
            >
              {estado.mensaje}
            </div>
          </div>
        )}

        {estado.tipo === "lista" && <Ficha ficha={estado.ficha} onExportar={() => exportar(estado.ficha)} />}
      </div>
    </>
  );
}

function Ficha({ ficha, onExportar }: { ficha: FichaEspecie; onExportar: () => void }) {
  const nombre = ficha.nombre_comun ?? ficha.nombre_cientifico;

  const etiquetas = [
    `${ficha.total_registros} registros`,
    ficha.elevacion,
  ].filter((e): e is string => Boolean(e));

  const datosClave: [string, string][] = [
    ["Nombre común", ficha.nombre_comun ?? SIN_DATO],
    ["Nombre científico", ficha.nombre_cientifico],
    ["Familia", ficha.familia],
    ["Hábitat", ficha.habitat ?? SIN_DATO],
    ["Elevación", ficha.elevacion ?? SIN_DATO],
  ];

  return (
    <>
      {/* Portada de la especie */}
      <div className="px-8 py-8" style={{ background: "#2d5a3d" }}>
        <div className="max-w-4xl">
          <div className="text-xs font-medium tracking-widest mb-2" style={{ color: "#a8d4b0", letterSpacing: "0.15em" }}>
            {ficha.familia.toUpperCase()}
          </div>
          <h2 className="text-4xl font-bold mb-1" style={{ color: "#ffffff", fontFamily: "'Lora', serif" }}>
            {nombre}
          </h2>
          <p className="text-lg italic mb-4" style={{ color: "#c5e8cc" }}>
            {ficha.nombre_cientifico}
          </p>
          <div className="flex flex-wrap gap-2">
            {etiquetas.map((t) => (
              <span
                key={t}
                className="text-xs px-3 py-1.5 rounded-full"
                style={{ background: "rgba(255,255,255,0.15)", color: "#e8f0eb" }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="px-8 py-6 max-w-4xl">
        <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 280px" }}>
          <div className="flex flex-col gap-5">
            <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <h3 className="font-semibold mb-3" style={{ color: "#1e3d2a" }}>
                Descripción general
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: "#374a3c" }}>
                {ficha.descripcion ?? "No hay una descripción disponible para esta especie."}
              </p>
            </div>

            <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <h3 className="font-semibold mb-3" style={{ color: "#1e3d2a" }}>
                Registros de presencia ({ficha.total_registros})
              </h3>
              {ficha.registros.length === 0 ? (
                <p className="text-sm" style={{ color: "#6b8f74" }}>
                  No hay registros de presencia para esta especie.
                </p>
              ) : (
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #dde8df" }}>
                  <table className="w-full text-xs">
                    <thead style={{ background: "#f0f5f1" }}>
                      <tr>
                        {["Localidad", "Fecha", "Coordenadas", "Elevación"].map((h) => (
                          <th key={h} className="px-3 py-2 text-left font-medium" style={{ color: "#374a3c" }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {ficha.registros.map((r, i) => (
                        <tr key={i} style={{ borderTop: "1px solid #dde8df" }}>
                          <td className="px-3 py-2" style={{ color: "#374a3c" }}>{r.localidad}</td>
                          <td className="px-3 py-2" style={{ color: "#6b8f74" }}>{r.fecha}</td>
                          <td className="px-3 py-2" style={{ color: "#6b8f74", fontFamily: "monospace" }}>
                            {r.latitud.toFixed(4)}, {r.longitud.toFixed(4)}
                          </td>
                          <td className="px-3 py-2" style={{ color: "#6b8f74" }}>
                            {r.elevacion_m !== null ? `${r.elevacion_m} m` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <h3 className="font-semibold mb-3" style={{ color: "#1e3d2a" }}>
                Fuentes consultadas
              </h3>
              <div className="flex flex-wrap gap-2">
                {ficha.fuentes.map((f) => (
                  <span
                    key={f}
                    className="text-xs px-3 py-1 rounded-full font-medium"
                    style={{ border: "1px solid #c5dccb", color: "#2d5a3d", background: "#f0f5f1" }}
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="rounded-2xl p-5" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <h3 className="font-semibold mb-3 text-sm" style={{ color: "#1e3d2a" }}>
                Datos clave
              </h3>
              {datosClave.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 py-2 text-xs" style={{ borderBottom: "1px solid #f0f5f1" }}>
                  <span style={{ color: "#8aab92" }}>{k}</span>
                  <span className="font-medium text-right" style={{ color: "#374a3c", maxWidth: "60%" }}>
                    {v}
                  </span>
                </div>
              ))}
            </div>
            <button
              onClick={onExportar}
              className="w-full flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium"
              style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Exportar ficha
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
