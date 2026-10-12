/**
 * Tarjeta de una respuesta del agente — RR_07, RR_08, RR_10, RR_14, RR_15,
 * RR_18 y RR_20: texto, mapa o lista de registros, fuentes, copiar, descargar
 * y acceso a la ficha.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { Copy, Download, ExternalLink, MapPin } from "lucide-react";
import { Avisos } from "./Avisos";
import type { RespuestaConsulta } from "../types";
import { descargarArchivo, descargarSvg, nombreBase, respuestaATexto } from "../utils/descarga";
import { RANGO_VACIO, filtrarPorElevacion, type RangoElevacion } from "../utils/elevacion";
import { DetallePunto, FiltroElevacion, MapaDistribucion } from "./Mapa";
import { CELDA_VACIA, COLUMNAS_TABLA_REGISTROS, formatearCoordenadas } from "../config/textos";

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
        style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)", maxWidth: 560, borderTopLeftRadius: 6 }}
      >
        <div className="px-6 py-5" style={{ background: "var(--color-marca)" }}>
          <div
            className="text-xs font-medium mb-1"
            style={{ color: "var(--color-sobre-marca-suave)", letterSpacing: "0.12em" }}
          >
            {respuesta.especie.familia}
          </div>
          <div className="text-2xl font-semibold italic" style={{ color: "var(--color-sobre-marca)", fontFamily: "var(--font-serif)" }}>
            {respuesta.especie.nombre_cientifico}
          </div>
          {respuesta.especie.nombre_comun && (
            <div className="text-sm mt-0.5" style={{ color: "var(--color-sobre-marca-tenue)" }}>
              {respuesta.especie.nombre_comun}
            </div>
          )}
          <div className="flex items-center gap-4 mt-3 flex-wrap">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{ background: "var(--color-etiqueta-sobre-marca)", color: "var(--color-sobre-marca-claro)" }}
            >
              {respuesta.total_registros} registros
            </span>
            {respuesta.elevacion && (
              <span
                className="text-xs px-2 py-1 rounded-full"
                style={{ background: "var(--color-etiqueta-sobre-marca)", color: "var(--color-sobre-marca-claro)" }}
              >
                {respuesta.elevacion}
              </span>
            )}
          </div>
        </div>

        <div className="px-6 py-5">
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-texto-cuerpo)" }}>
            {respuesta.texto}
          </p>

          {/* RR_43 y RR_58: por qué falta el mapa o los registros. */}
          <Avisos avisos={respuesta.avisos} className="mt-4" />

          {respuesta.registros.length > 0 && (
            <>
              {/* RR_18 cambiar entre la vista de mapa y la de lista. */}
              <div
                className="flex gap-1 mt-4 mb-3 p-1 rounded-xl"
                style={{ background: "var(--color-superficie-suave)", width: "fit-content" }}
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
                      background: vista === v ? "var(--color-marca)" : "transparent",
                      color: vista === v ? "var(--color-sobre-marca)" : "var(--color-texto-secundario)",
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
                    <MapPin size={14} style={{ color: "var(--color-marca)" }} />
                    <span className="text-sm font-medium" style={{ color: "var(--color-texto-marca)" }}>
                      Distribución en Costa Rica
                    </span>
                    {/* RR_15 — descargar el mapa mostrado. */}
                    <button
                      onClick={descargarMapa}
                      className="ml-auto flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs transition-all"
                      style={{ background: "transparent", color: "var(--color-texto-tenue)", border: "none", cursor: "pointer" }}
                    >
                      <Download size={12} />
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
                  <div className="rounded-xl overflow-hidden" style={{ height: 170, border: "1px solid var(--color-borde)" }}>
                    <MapaDistribucion
                      ref={mapaRef}
                      registros={respuesta.registros}
                      indices={filtro.indices}
                      seleccionado={seleccionado}
                      onSeleccionar={setSeleccionado}
                    />
                  </div>
                  {filtro.activo && filtro.indices.length === 0 ? (
                    <p role="status" className="mt-1.5 text-xs" style={{ color: "var(--color-aviso-texto)" }}>
                      Ningún registro está dentro de ese rango de elevación. Ajusta el rango o quita el filtro.
                    </p>
                  ) : seleccionado !== null && respuesta.registros[seleccionado] ? (
                    <DetallePunto registro={respuesta.registros[seleccionado]} onCerrar={cerrarDetalle} />
                  ) : (
                    <p className="mt-1.5 text-xs" style={{ color: "var(--color-texto-tenue)" }}>
                      Haz clic en un punto para ver el detalle del registro.
                    </p>
                  )}
                </>
              ) : (
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--color-borde)" }}>
                  <table className="w-full text-xs">
                    <thead style={{ background: "var(--color-superficie-suave)" }}>
                      <tr>
                        {COLUMNAS_TABLA_REGISTROS.map((h) => (
                          <th key={h} className="px-3 py-2 text-left font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {respuesta.registros.map((r, i) => (
                        <tr key={i} style={{ borderTop: "1px solid var(--color-borde)" }}>
                          <td className="px-3 py-2" style={{ color: "var(--color-texto-cuerpo)" }}>{r.localidad}</td>
                          <td className="px-3 py-2" style={{ color: "var(--color-texto-secundario)" }}>{r.fecha}</td>
                          <td className="px-3 py-2" style={{ color: "var(--color-texto-secundario)", fontFamily: "var(--font-mono)" }}>
                            {formatearCoordenadas(r)}
                          </td>
                          <td className="px-3 py-2" style={{ color: "var(--color-texto-secundario)" }}>
                            {r.elevacion_m !== null ? `${r.elevacion_m} m` : CELDA_VACIA}
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
              <span className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>Fuentes:</span>
              {respuesta.fuentes.map((f) => (
                <span
                  key={f}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{ border: "1px solid var(--color-borde-fuerte)", color: "var(--color-texto-marca)", background: "var(--color-superficie-suave)", fontWeight: 500 }}
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
                  background: copiado ? "var(--color-superficie-marca)" : "transparent",
                  color: copiado ? "var(--color-texto-marca)" : "var(--color-texto-tenue)",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <Copy size={12} />
                {copiado ? "Copiado" : "Copiar"}
              </button>
              {/* RR_15 — descargar la respuesta como texto. */}
              <button
                onClick={descargarRespuesta}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{ background: "transparent", color: "var(--color-texto-tenue)", border: "none", cursor: "pointer" }}
              >
                <Download size={12} />
                Descargar
              </button>
              <button
                onClick={() => onVerFicha(respuesta.especie.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{ background: "transparent", color: "var(--color-texto-tenue)", border: "none", cursor: "pointer" }}
              >
                <ExternalLink size={12} />
                Ficha completa
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
