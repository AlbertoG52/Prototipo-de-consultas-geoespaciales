/**
 * Tarjeta de una respuesta del agente — RR_07, RR_08, RR_10, RR_14, RR_15,
 * RR_18 y RR_20: texto, mapa o lista de registros, fuentes, copiar, descargar
 * y acceso a la ficha.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import type { RespuestaConsulta } from "../types";
import { descargarArchivo, descargarSvg, nombreBase, respuestaATexto } from "../utils/descarga";
import { RANGO_VACIO, filtrarPorElevacion, type RangoElevacion } from "../utils/elevacion";
import { DetallePunto, FiltroElevacion, MapaDistribucion } from "./Mapa";

function IconoDescarga() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function TarjetaRespuesta({
  consulta,
  respuesta,
  onVerFicha,
}: {
  consulta: string;
  respuesta: RespuestaConsulta;
  /** RR_20 criterio 3 — abre la ficha de la especie de esta respuesta (por su id). */
  onVerFicha: (especieId: string) => void;
}) {
  const [copiado, setCopiado] = useState(false);
  // RR_18 — el usuario alterna entre las dos vistas de los mismos registros.
  const [vista, setVista] = useState<"mapa" | "lista">("mapa");
  const mapaRef = useRef<SVGSVGElement>(null);
  // RR_12 — punto del mapa cuyo detalle está abierto (índice en respuesta.registros).
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const cerrarDetalle = useCallback(() => setSeleccionado(null), []);
  // RR_19 — rango de elevación del filtro del mapa ("" = sin límite).
  const [rango, setRango] = useState<RangoElevacion>(RANGO_VACIO);
  const filtro = filtrarPorElevacion(respuesta.registros, rango);

  // Si el filtro oculta el punto cuyo detalle está abierto, el detalle se cierra
  // (RR_12 criterio 2: el detalle siempre corresponde a un punto visible).
  useEffect(() => {
    if (seleccionado !== null && !filtro.indices.includes(seleccionado)) setSeleccionado(null);
  }, [seleccionado, filtro.indices]);

  /** RR_15 — la respuesta completa, con la consulta que la originó. */
  const descargarRespuesta = () => {
    descargarArchivo(
      `${nombreBase(respuesta)}.txt`,
      respuestaATexto(consulta, respuesta),
      "text/plain;charset=utf-8",
    );
  };

  /**
   * RR_15 — el mapa tal como se muestra. El botón solo existe en la vista de
   * mapa, así que el SVG siempre está montado cuando se usa.
   */
  const descargarMapa = () => {
    if (mapaRef.current) descargarSvg(mapaRef.current, `${nombreBase(respuesta)}-mapa.svg`);
  };

  /** RR_10 — copiar el texto de la respuesta y confirmarlo visualmente. */
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(respuesta.texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      /* el navegador puede bloquear el portapapeles sin HTTPS */
    }
  };

  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl overflow-hidden w-full"
        style={{ background: "#ffffff", border: "1px solid #dde8df", maxWidth: 560, borderTopLeftRadius: 6 }}
      >
        <div className="px-6 py-5" style={{ background: "#2d5a3d" }}>
          <div
            className="text-xs font-medium mb-1"
            style={{ color: "#a8d4b0", letterSpacing: "0.12em" }}
          >
            {respuesta.especie.familia}
          </div>
          <div className="text-2xl font-bold" style={{ color: "#ffffff", fontFamily: "'Lora', serif" }}>
            {respuesta.especie.nombre_comun ?? respuesta.especie.nombre_cientifico}
          </div>
          <div className="text-sm italic mt-0.5" style={{ color: "#c5e8cc" }}>
            {respuesta.especie.nombre_cientifico}
          </div>
          <div className="flex items-center gap-4 mt-3 flex-wrap">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{ background: "rgba(255,255,255,0.15)", color: "#e8f0eb" }}
            >
              {respuesta.total_registros} registros
            </span>
            {respuesta.elevacion && (
              <span
                className="text-xs px-2 py-1 rounded-full"
                style={{ background: "rgba(255,255,255,0.15)", color: "#e8f0eb" }}
              >
                {respuesta.elevacion}
              </span>
            )}
          </div>
        </div>

        <div className="px-6 py-5">
          <p className="text-sm leading-relaxed" style={{ color: "#374a3c" }}>
            {respuesta.texto}
          </p>

          {respuesta.registros.length > 0 && (
            <>
              {/* RR_18 cambiar entre la vista de mapa y la de lista. */}
              <div
                className="flex gap-1 mt-4 mb-3 p-1 rounded-xl"
                style={{ background: "#f0f5f1", width: "fit-content" }}
                role="group"
                aria-label="Vista de los registros"
              >
                {(["mapa", "lista"] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => {
                      setVista(v);
                      setSeleccionado(null);
                    }}
                    aria-pressed={vista === v}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: vista === v ? "#2d5a3d" : "transparent",
                      color: vista === v ? "#fff" : "#6b8f74",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    {v === "mapa" ? "Mapa" : "Lista de registros"}
                  </button>
                ))}
              </div>

              {/*
                RR_18 ambas vistas muestran la misma especie:
                las dos leen `respuesta.registros`, no dos fuentes distintas.
              */}
              {vista === "mapa" ? (
                <>
                  <div className="flex items-center gap-1.5 mb-2">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#2d5a3d" />
                      <circle cx="12" cy="9" r="2.5" fill="white" />
                    </svg>
                    <span className="text-sm font-medium" style={{ color: "#2d5a3d" }}>
                      Distribución en Costa Rica
                    </span>
                    {/* RR_15 — descargar el mapa mostrado. */}
                    <button
                      onClick={descargarMapa}
                      className="ml-auto flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs transition-all"
                      style={{ background: "transparent", color: "#8aab92", border: "none", cursor: "pointer" }}
                    >
                      <IconoDescarga />
                      Descargar mapa
                    </button>
                  </div>
                  {/* RR_19 — va dentro de la vista de mapa: si el mapa no se muestra, tampoco el filtro. */}
                  <FiltroElevacion
                    rango={rango}
                    onCambiar={setRango}
                    visibles={filtro.indices.length}
                    total={respuesta.registros.length}
                    activo={filtro.activo}
                    error={filtro.error}
                  />
                  <div className="rounded-xl overflow-hidden" style={{ height: 170, border: "1px solid #dde8df" }}>
                    <MapaDistribucion
                      ref={mapaRef}
                      registros={respuesta.registros}
                      indices={filtro.indices}
                      seleccionado={seleccionado}
                      onSeleccionar={setSeleccionado}
                    />
                  </div>
                  {filtro.activo && filtro.indices.length === 0 ? (
                    <p role="status" className="mt-1.5 text-xs" style={{ color: "#7a5a00" }}>
                      Ningún registro está dentro de ese rango de elevación. Ajusta el rango o quita el filtro.
                    </p>
                  ) : seleccionado !== null && respuesta.registros[seleccionado] ? (
                    <DetallePunto registro={respuesta.registros[seleccionado]} onCerrar={cerrarDetalle} />
                  ) : (
                    <p className="mt-1.5 text-xs" style={{ color: "#8aab92" }}>
                      Haz clic en un punto para ver el detalle del registro.
                    </p>
                  )}
                </>
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
                      {respuesta.registros.map((r, i) => (
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
            </>
          )}

          <div className="mt-4 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm" style={{ color: "#6b8f74" }}>Fuentes:</span>
              {respuesta.fuentes.map((f) => (
                <span
                  key={f}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{ border: "1px solid #c5dccb", color: "#2d5a3d", background: "#f0f5f1", fontWeight: 500 }}
                >
                  {f}
                </span>
              ))}
            </div>
            <div className="flex items-center gap-1">
              {/* RR_10 — botón visible, y confirmación visual al copiar. */}
              <button
                onClick={copiar}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{
                  background: copiado ? "#e8f0eb" : "transparent",
                  color: copiado ? "#2d5a3d" : "#8aab92",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" strokeWidth="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke="currentColor" strokeWidth="2" />
                </svg>
                {copiado ? "Copiado" : "Copiar"}
              </button>
              {/* RR_15 — descargar la respuesta como texto. */}
              <button
                onClick={descargarRespuesta}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{ background: "transparent", color: "#8aab92", border: "none", cursor: "pointer" }}
              >
                <IconoDescarga />
                Descargar
              </button>
              <button
                onClick={() => onVerFicha(respuesta.especie.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{ background: "transparent", color: "#8aab92", border: "none", cursor: "pointer" }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Ficha completa
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
