/**
 * Mapa de distribución de CR-BioLM y controles de los registros — RR_46,
 * RR_52, RR_53, RR_12 y RR_19.
 *
 * Todos los mapas vienen de CR-BioLM (PNG). Si la respuesta no trae mapa, no
 * se muestra ninguno. El detalle de un registro (RR_12) y el filtro por
 * elevación (RR_19) trabajan sobre la tabla de registros, porque en una imagen
 * no se puede seleccionar ni ocultar puntos.
 */
import { useEffect, useState } from "react";

import { Download, X } from "lucide-react";
import * as api from "../services/api";
import type { MapaEspecie, RegistroPresencia } from "../types";
import { RANGO_VACIO, type RangoElevacion } from "../utils/elevacion";
import { ETIQUETAS_REGISTRO, formatearCoordenadas, SIN_DATO, textoRegistros } from "../config/textos";

type EstadoImagen =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; url: string };

/**
 * Descarga el PNG del mapa con la sesión y lo convierte en una URL local
 * (blob:). La URL se libera al desmontar el componente o al cambiar de mapa.
 */
function useImagenMapa(ruta: string): EstadoImagen {
  const [estado, setEstado] = useState<EstadoImagen>({ tipo: "cargando" });

  useEffect(() => {
    let vigente = true;
    let url: string | null = null;
    setEstado({ tipo: "cargando" });
    api
      .obtenerImagenMapa(ruta)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        // Si el componente ya se desmontó, la URL no llega a usarse.
        if (vigente) setEstado({ tipo: "lista", url });
        else URL.revokeObjectURL(url);
      })
      .catch((err) => {
        if (!vigente) return;
        const mensaje =
          err instanceof api.ErrorApi && err.status === 404
            ? "CR-BioLM no tiene un mapa disponible para esta especie."
            : "No se pudo cargar el mapa. Intenta de nuevo más tarde.";
        setEstado({ tipo: "error", mensaje });
      });
    return () => {
      vigente = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [ruta]);

  return estado;
}

/**
 * RR_46 — mapa de distribución generado por CR-BioLM.
 *
 * - Criterio 1: solo se monta cuando la respuesta trae `mapa` (hay datos
 *   geoespaciales); quien lo usa no lo muestra si `mapa` es null (RR_53).
 * - Criterio 2: la imagen es la de CR-BioLM, con las zonas de distribución.
 * - Criterio 3: el texto alternativo y el título nombran la especie.
 *
 * RR_15: "Descargar mapa" baja este mismo PNG.
 * RR_59: debajo del mapa se indica cuántos registros de GBIF tiene dibujados.
 */
export function MapaCRBioLM({
  mapa,
  especie,
  nombreArchivo,
}: {
  mapa: MapaEspecie;
  /** Nombre científico de la especie del mapa. */
  especie: string;
  /** Nombre del archivo al descargar el mapa (RR_15). */
  nombreArchivo: string;
}) {
  const imagen = useImagenMapa(mapa.url);

  return (
    <figure className="m-0">
      {imagen.tipo === "lista" && (
        <div className="flex justify-end mb-1">
          <a
            href={imagen.url}
            download={nombreArchivo}
            className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs transition-all"
            style={{ color: "var(--color-texto-tenue)", textDecoration: "none" }}
          >
            <Download size={12} />
            Descargar mapa
          </a>
        </div>
      )}
      <div
        className="rounded-xl overflow-hidden flex items-center justify-center"
        style={{ border: "1px solid var(--color-borde)", background: "var(--color-superficie-suave)", minHeight: 170 }}
      >
        {imagen.tipo === "cargando" && (
          <p role="status" className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>
            Cargando el mapa…
          </p>
        )}
        {imagen.tipo === "error" && (
          <p role="alert" className="text-xs px-4 text-center" style={{ color: "var(--color-texto-secundario)" }}>
            {imagen.mensaje}
          </p>
        )}
        {imagen.tipo === "lista" && (
          <img
            src={imagen.url}
            alt={`Mapa de distribución de ${especie} en Costa Rica, generado por CR-BioLM.`}
            className="w-full h-auto block"
          />
        )}
      </div>
      <figcaption className="mt-1.5 text-xs flex flex-col gap-0.5">
        {/* RR_59 criterio 2: la cantidad de registros junto al mapa. */}
        {mapa.puntos > 0 && (
          <span style={{ color: "var(--color-texto-secundario)" }}>
            {textoRegistros(mapa.puntos)} de presencia de GBIF en el mapa
          </span>
        )}
        {/* Aviso de CR-BioLM sobre el mapa, si lo hay. */}
        {mapa.advertencia && <span style={{ color: "var(--color-aviso-texto)" }}>{mapa.advertencia}</span>}
      </figcaption>
    </figure>
  );
}

/**
 * RR_12 — detalle del punto seleccionado.
 *
 * Va debajo de la tabla de registros. Se cierra con la X, con Escape o
 * volviendo a hacer clic en la misma fila.
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
    [ETIQUETAS_REGISTRO.localidad, registro.localidad],
    [ETIQUETAS_REGISTRO.fechaDelRegistro, registro.fecha],
    [ETIQUETAS_REGISTRO.coordenadas, formatearCoordenadas(registro)],
    [ETIQUETAS_REGISTRO.elevacion, registro.elevacion_m !== null ? `${registro.elevacion_m} msnm` : SIN_DATO],
    [ETIQUETAS_REGISTRO.fuente, registro.fuente],
  ];

  return (
    <div
      role="region"
      aria-live="polite"
      aria-label={`Detalle del registro en ${registro.localidad}`}
      className="mt-2 rounded-xl px-4 py-3 text-xs"
      style={{ background: "var(--color-superficie-suave)", border: "1px solid var(--color-borde-fuerte)" }}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="flex items-center gap-1.5 font-semibold" style={{ color: "var(--color-texto)" }}>
          <span className="inline-block rounded-full" style={{ width: 8, height: 8, background: "var(--color-mapa-activo)" }} />
          Detalle del registro
        </span>
        <button
          onClick={onCerrar}
          aria-label="Cerrar detalle"
          className="flex items-center gap-1 px-2 py-1 rounded-md"
          style={{ border: "none", background: "transparent", color: "var(--color-texto-secundario)", cursor: "pointer" }}
        >
          <X size={12} />
          Cerrar
        </button>
      </div>
      <dl className="grid gap-x-4 gap-y-1" style={{ gridTemplateColumns: "auto 1fr" }}>
        {filas.map(([k, v]) => (
          <div key={k} className="contents">
            <dt style={{ color: "var(--color-texto-tenue)" }}>{k}</dt>
            <dd className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>
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
    border: `1.5px solid ${error ? "var(--color-error-borde)" : "var(--color-borde-fuerte)"}`,
    background: "var(--color-fondo)",
    color: "var(--color-texto)",
  };

  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 flex-wrap text-xs" role="group" aria-label="Filtrar por elevación">
        <span className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>
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
        <span style={{ color: "var(--color-texto-tenue)" }}>a</span>
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
            style={{ border: "1px solid var(--color-borde-fuerte)", background: "transparent", color: "var(--color-texto-marca)", cursor: "pointer" }}
          >
            Quitar filtro
          </button>
        )}
        {activo && (
          <span aria-live="polite" style={{ color: "var(--color-texto-secundario)" }}>
            Mostrando {visibles} de {total} registros
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className="text-xs mt-1" style={{ color: "var(--color-error-texto)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
