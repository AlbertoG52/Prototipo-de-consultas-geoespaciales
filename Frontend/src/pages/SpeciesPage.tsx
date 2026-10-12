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

import { ArrowLeft, Download } from "lucide-react";
import { Avisos } from "../components/Avisos";
import { PREFIJO_ARCHIVOS } from "../config/marca";
import * as api from "../services/api";
import type { FichaEspecie } from "../types";
import { descargarArchivo, fichaATexto } from "../utils/descarga";
import { CELDA_VACIA, COLUMNAS_TABLA_REGISTROS, ETIQUETAS_REGISTRO, formatearCoordenadas, SIN_DATO } from "../config/textos";

type Estado =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; ficha: FichaEspecie };

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
    descargarArchivo(`${PREFIJO_ARCHIVOS}-ficha-${ficha.id}.txt`, fichaATexto(ficha), "text/plain;charset=utf-8");

  return (
    <>
      {/* Encabezado */}
      <div
        className="px-8 py-4 border-b shrink-0 flex items-center gap-3"
        style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}
      >
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm transition-all rounded-lg px-3 py-2"
          style={{ color: "var(--color-texto-secundario)", border: "none", background: "transparent", cursor: "pointer" }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "var(--color-superficie-suave)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          }}
        >
          <ArrowLeft size={16} />
          Volver a consultas
        </button>
        <span style={{ color: "var(--color-borde)" }}>|</span>
        <h1 className="text-base font-medium" style={{ color: "var(--color-texto)" }}>
          Ficha completa de especie
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ background: "var(--color-fondo)" }}>
        {estado.tipo === "cargando" && (
          <div className="px-8 py-10 text-sm" role="status" style={{ color: "var(--color-texto-secundario)" }}>
            Cargando la ficha…
          </div>
        )}

        {estado.tipo === "error" && (
          <div className="px-8 py-10 max-w-xl">
            <div
              role="alert"
              className="rounded-xl p-4 text-sm"
              style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", color: "var(--color-error-texto)" }}
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
  const etiquetas = [
    `${ficha.total_registros} registros`,
    ficha.elevacion,
  ].filter((e): e is string => Boolean(e));

  // El nombre científico identifica a la especie; el común solo se muestra si
  // existe (muchas plantas no tienen uno).
  const datosClave: [string, string][] = [
    ["Nombre científico", ficha.nombre_cientifico],
    ...(ficha.nombre_comun ? [["Nombre común", ficha.nombre_comun] as [string, string]] : []),
    ["Familia", ficha.familia],
    ["Hábitat", ficha.habitat ?? SIN_DATO],
    [ETIQUETAS_REGISTRO.elevacion, ficha.elevacion ?? SIN_DATO],
  ];

  return (
    <>
      {/* Portada de la especie */}
      <div className="px-8 py-8" style={{ background: "var(--color-marca)" }}>
        <div className="max-w-4xl">
          <div className="text-xs font-medium tracking-widest mb-2" style={{ color: "var(--color-sobre-marca-suave)", letterSpacing: "0.15em" }}>
            {ficha.familia.toUpperCase()}
          </div>
          <h2
            className={`text-4xl font-semibold italic ${ficha.nombre_comun ? "mb-1" : "mb-4"}`}
            style={{ color: "var(--color-sobre-marca)", fontFamily: "var(--font-serif)" }}
          >
            {ficha.nombre_cientifico}
          </h2>
          {ficha.nombre_comun && (
            <p className="text-lg mb-4" style={{ color: "var(--color-sobre-marca-tenue)" }}>
              {ficha.nombre_comun}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {etiquetas.map((t) => (
              <span
                key={t}
                className="text-xs px-3 py-1.5 rounded-full"
                style={{ background: "var(--color-etiqueta-sobre-marca)", color: "var(--color-sobre-marca-claro)" }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="px-8 py-6 max-w-4xl">
        {/* RR_43 y RR_58: por qué falta el mapa o los registros. */}
        <Avisos avisos={ficha.avisos} className="mb-6" />
        <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 280px" }}>
          <div className="flex flex-col gap-5">
            <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
              <h3 className="font-semibold mb-3" style={{ color: "var(--color-texto)" }}>
                Descripción general
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: "var(--color-texto-cuerpo)" }}>
                {ficha.descripcion ?? "No hay una descripción disponible para esta especie."}
              </p>
            </div>

            <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
              <h3 className="font-semibold mb-3" style={{ color: "var(--color-texto)" }}>
                Registros de presencia ({ficha.total_registros})
              </h3>
              {ficha.registros.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>
                  No hay registros de presencia para esta especie.
                </p>
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
                      {ficha.registros.map((r, i) => (
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
            </div>

            <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
              <h3 className="font-semibold mb-3" style={{ color: "var(--color-texto)" }}>
                Fuentes consultadas
              </h3>
              <div className="flex flex-wrap gap-2">
                {ficha.fuentes.map((f) => (
                  <span
                    key={f}
                    className="text-xs px-3 py-1 rounded-full font-medium"
                    style={{ border: "1px solid var(--color-borde-fuerte)", color: "var(--color-texto-marca)", background: "var(--color-superficie-suave)" }}
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="rounded-2xl p-5" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
              <h3 className="font-semibold mb-3 text-sm" style={{ color: "var(--color-texto)" }}>
                Datos clave
              </h3>
              {datosClave.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 py-2 text-xs" style={{ borderBottom: "1px solid var(--color-superficie-suave)" }}>
                  <span style={{ color: "var(--color-texto-tenue)" }}>{k}</span>
                  <span className="font-medium text-right" style={{ color: "var(--color-texto-cuerpo)", maxWidth: "60%" }}>
                    {v}
                  </span>
                </div>
              ))}
            </div>
            <button
              onClick={onExportar}
              className="w-full flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium"
              style={{ background: "var(--color-marca)", color: "var(--color-sobre-marca)", border: "none", cursor: "pointer" }}
            >
              <Download size={14} />
              Exportar ficha
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
