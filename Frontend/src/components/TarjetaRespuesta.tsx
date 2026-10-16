/**
 * Tarjeta de una respuesta del agente — RR_07, RR_08, RR_10, RR_14, RR_15,
 * RR_18, RR_20 y RR_46: texto, mapa de CR-BioLM o lista de registros, fuentes,
 * copiar, descargar y acceso a la ficha.
 *
 * RR_50 y RR_51: fuentes de la respuesta, cita de la fuente debajo del texto y
 * si la información viene del Manual de Plantas (MPCR), de GBIF o de ambas.
 *
 * RR_49: si el texto lo redactó el LLM de CR-BioLM, trae las citas del Manual
 * dentro (【…】); se muestran como cita, p. ej. "(Tomo V, p.779)".
 *
 * RR_12 (detalle de un registro) y RR_19 (filtro por elevación) viven en la
 * lista de registros: el mapa es un PNG de CR-BioLM y no permite seleccionar
 * ni ocultar puntos.
 */
import { useCallback, useEffect, useState } from "react";

import { Copy, Download, ExternalLink, MapPin } from "lucide-react";
import { Avisos } from "./Avisos";
import { OrigenDeLosDatos } from "./OrigenDeLosDatos";
import type { RespuestaConsulta } from "../types";
import { descargarArchivo, nombreBase, respuestaATexto } from "../utils/descarga";
import { RANGO_VACIO, filtrarPorElevacion, type RangoElevacion } from "../utils/elevacion";
import { origenDeLaInformacion, partirCitas, procedenciaDe } from "../utils/fuentes";
import { mapaDeLaEspecie } from "../utils/mapa";
import { DetallePunto, FiltroElevacion, MapaCRBioLM } from "./Mapa";
import { CELDA_VACIA, COLUMNAS_TABLA_REGISTROS, formatearCoordenadas, IDIOMA_FECHAS, textoRegistros } from "../config/textos";

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
  // RR_53 criterio 3: solo hay mapa si CR-BioLM lo generó (mapa != null).
  // RR_54: y solo si es el de la especie de esta respuesta.
  const mapa = mapaDeLaEspecie(respuesta.mapa, respuesta.especie.id) ? respuesta.mapa : null;
  const hayMapa = mapa !== null;
  const hayRegistros = respuesta.registros.length > 0;
  // RR_18 — el usuario alterna entre el mapa y la lista de registros. Si falta
  // una de las dos, se muestra la que haya.
  const [vistaElegida, setVista] = useState<"mapa" | "lista">("mapa");
  // Sin mapa no se muestra este bloque (ver abajo), así que solo importa con mapa.
  const vista = !hayRegistros ? "mapa" : vistaElegida;
  // RR_12 — registro cuyo detalle está abierto (índice en respuesta.registros).
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const cerrarDetalle = useCallback(() => setSeleccionado(null), []);
  // RR_19 — rango de elevación del filtro de la lista ("" = sin límite).
  const [rango, setRango] = useState<RangoElevacion>(RANGO_VACIO);
  const filtro = filtrarPorElevacion(respuesta.registros, rango);
  // RR_51 — de dónde sale el texto, los registros y la respuesta en general.
  const citaTexto = procedenciaDe(respuesta.procedencia, "texto");
  const fuenteRegistros = procedenciaDe(respuesta.procedencia, "registros");
  const origen = origenDeLaInformacion(respuesta.procedencia);

  // RR_12 — lugar del registro abierto entre los visibles, para recorrerlos.
  const posicionVisible = seleccionado === null ? -1 : filtro.indices.indexOf(seleccionado);

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
        <div className="px-4 sm:px-6 py-5" style={{ background: "var(--color-marca)" }}>
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
            {/* RR_59: cantidad de registros encontrados ("Sin registros" si no hay).
                Se omite solo si GBIF no respondió (RR_58): el aviso lo explica. */}
            {fuenteRegistros && (
              <span
                className="text-xs px-2 py-1 rounded-full"
                style={{ background: "var(--color-etiqueta-sobre-marca)", color: "var(--color-sobre-marca-claro)" }}
              >
                {textoRegistros(respuesta.total_registros)}
              </span>
            )}
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

        <div className="px-4 sm:px-6 py-5">
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-texto-cuerpo)" }}>
            {/* RR_49 / RR_51: las citas del Manual dentro del texto, con formato de cita. */}
            {partirCitas(respuesta.texto).map((trozo, i) =>
              trozo.tipo === "texto" ? (
                <span key={i}>{trozo.valor}</span>
              ) : (
                <cite key={i} title={trozo.completa} className="not-italic text-xs ml-0.5" style={{ color: "var(--color-texto-tenue)" }}>
                  ({trozo.valor})
                </cite>
              ),
            )}
          </p>
          {/* RR_51 criterio 2: cita específica de la fuente del texto. */}
          {citaTexto && (
            <p className="mt-1.5 text-xs" style={{ color: "var(--color-texto-tenue)" }}>
              — <cite className="not-italic">{citaTexto.fuente}, {citaTexto.detalle}</cite>
            </p>
          )}

          {/* RR_43 y RR_58: por qué falta el mapa o los registros. */}
          <Avisos avisos={respuesta.avisos} className="mt-4" />

          {/* Sin mapa, la respuesta queda solo con el texto: no se muestra ni el
              mapa ni la lista de registros. La cantidad sigue en la etiqueta del
              encabezado (RR_59) y los registros, en la ficha completa. */}
          {hayMapa && (
            <>
              {/* RR_18 cambiar entre la vista de mapa y la de lista (si hay las dos). */}
              {hayMapa && hayRegistros && (
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
              )}

              {/* RR_18 ambas vistas son de la misma especie de la respuesta. */}
              {vista === "mapa" && mapa ? (
                <div className={hayRegistros ? "" : "mt-4"}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <MapPin size={14} style={{ color: "var(--color-marca)" }} />
                    <span className="text-sm font-medium" style={{ color: "var(--color-texto-marca)" }}>
                      Distribución en Costa Rica
                    </span>
                  </div>
                  <MapaCRBioLM
                    mapa={mapa}
                    especie={respuesta.especie.nombre_cientifico}
                    nombreArchivo={`${nombreBase(respuesta)}-mapa.png`}
                  />
                </div>
              ) : (
                <div className={hayMapa ? "" : "mt-4"}>
                  {/* RR_59: CR-BioLM entrega como máximo 500 puntos; si hay más, se aclara. */}
                  {respuesta.registros.length < respuesta.total_registros && (
                    <p className="mb-2 text-xs" style={{ color: "var(--color-texto-secundario)" }}>
                      Se muestran {textoRegistros(respuesta.registros.length)} de {respuesta.total_registros.toLocaleString(IDIOMA_FECHAS)}.
                    </p>
                  )}
                  {/* RR_51: la lista dice de qué fuente son los registros. */}
                  {fuenteRegistros && (
                    <p className="mb-2 text-xs" style={{ color: "var(--color-texto-secundario)" }}>
                      Registros de presencia de {fuenteRegistros.fuente}.
                    </p>
                  )}
                  {/* RR_19 — filtrar la lista por rango de elevación. */}
                  <FiltroElevacion
                    rango={rango}
                    onCambiar={setRango}
                    visibles={filtro.indices.length}
                    total={respuesta.registros.length}
                    activo={filtro.activo}
                    error={filtro.error}
                  />
                  {filtro.activo && filtro.indices.length === 0 ? (
                    <p role="status" className="mt-1.5 text-xs" style={{ color: "var(--color-aviso-texto)" }}>
                      Ningún registro está dentro de ese rango de elevación. Ajusta el rango o quita el filtro.
                    </p>
                  ) : (
                    <div className="rounded-xl overflow-x-auto" style={{ border: "1px solid var(--color-borde)" }}>
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
                          {filtro.indices.map((i) => {
                            const r = respuesta.registros[i];
                            const activo = i === seleccionado;
                            const alternar = () => setSeleccionado(activo ? null : i);
                            return (
                              <tr
                                key={i}
                                // RR_12 criterio 1: al seleccionar un registro se abre su detalle.
                                onClick={alternar}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    alternar();
                                  }
                                }}
                                tabIndex={0}
                                aria-selected={activo}
                                aria-label={`Registro en ${r.localidad}, ${r.fecha}. Ver detalle.`}
                                style={{
                                  borderTop: "1px solid var(--color-borde)",
                                  background: activo ? "var(--color-superficie-marca)" : "transparent",
                                  cursor: "pointer",
                                }}
                              >
                                <td className="px-3 py-2" style={{ color: "var(--color-texto-cuerpo)" }}>{r.localidad}</td>
                                <td className="px-3 py-2 whitespace-nowrap" style={{ color: "var(--color-texto-secundario)" }}>{r.fecha}</td>
                                <td className="px-3 py-2 whitespace-nowrap" style={{ color: "var(--color-texto-secundario)", fontFamily: "var(--font-mono)" }}>
                                  {formatearCoordenadas(r)}
                                </td>
                                <td className="px-3 py-2" style={{ color: "var(--color-texto-secundario)" }}>
                                  {r.elevacion_m !== null ? `${r.elevacion_m} m` : CELDA_VACIA}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {filtro.indices.length > 0 && (
                    <p className="mt-1.5 text-xs" style={{ color: "var(--color-texto-tenue)" }}>
                      Haz clic en un registro para ver su detalle.
                    </p>
                  )}
                  {seleccionado !== null && respuesta.registros[seleccionado] && (
                    <DetallePunto
                      registro={respuesta.registros[seleccionado]}
                      onCerrar={cerrarDetalle}
                      posicion={{ actual: posicionVisible + 1, total: filtro.indices.length }}
                      onAnterior={posicionVisible > 0 ? () => setSeleccionado(filtro.indices[posicionVisible - 1]) : undefined}
                      onSiguiente={
                        posicionVisible < filtro.indices.length - 1
                          ? () => setSeleccionado(filtro.indices[posicionVisible + 1])
                          : undefined
                      }
                    />
                  )}
                </div>
              )}
            </>
          )}

          {/* RR_51 criterio 1: si la información viene del MPCR, de GBIF o de ambas. */}
          {origen && (
            <p className="mt-4 text-xs" style={{ color: "var(--color-texto-secundario)" }}>
              Información de: <span className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>{origen}</span>
            </p>
          )}

          <div className={`${origen ? "mt-2" : "mt-4"} flex items-center justify-between flex-wrap gap-2`}>
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

          {/* RR_45: de dónde sale cada dato. */}
          <OrigenDeLosDatos procedencia={respuesta.procedencia} className="mt-3" />
        </div>
      </div>
    </div>
  );
}
