/**
 * RR_76 criterios 1 y 2 — historial de uso de una cuenta
 * (GET /admin/usuarios/{id}/consultas): sus consultas, de la más reciente a la
 * más antigua, por páginas.
 *
 * El texto de cada consulta lo manda el servidor solo si ADMIN_VE_TEXTO_CONSULTAS
 * está encendido (`texto_visible`); si no, se ve cuándo consultó, con qué
 * resultado y de qué especie.
 *
 * Quien lo usa le pone `key={usuario.id}`, así cada cuenta empieza de cero.
 */
import { useCallback, useEffect, useState } from "react";

import { X } from "lucide-react";
import { CELDA_VACIA, ETIQUETAS_ESTADO_CONSULTA, ETIQUETAS_ROL, IDIOMA_FECHAS, formatearNumero } from "../../config/textos";
import * as api from "../../services/api";
import type { ConsultaDeUsuario, HistorialUso, Usuario } from "../../types";

const POR_PAGINA = 20;

const COLORES_ESTADO: Record<ConsultaDeUsuario["estado"], { fondo: string; texto: string }> = {
  resuelta: { fondo: "var(--color-superficie-marca)", texto: "var(--color-texto-marca)" },
  ambigua: { fondo: "var(--color-aviso-fondo)", texto: "var(--color-aviso-texto)" },
  sin_coincidencias: { fondo: "var(--color-neutro-fondo)", texto: "var(--color-neutro)" },
};

const fecha = (iso: string) => new Date(iso).toLocaleString(IDIOMA_FECHAS);

interface Props {
  usuario: Usuario;
  alCerrar: () => void;
}

export function HistorialDeUso({ usuario, alCerrar }: Props) {
  const [historial, setHistorial] = useState<HistorialUso | null>(null);
  const [consultas, setConsultas] = useState<ConsultaDeUsuario[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  /** Pide la página que empieza en `desplazamiento` y la agrega a la lista. */
  const cargar = useCallback(
    async (desplazamiento: number) => {
      setCargando(true);
      setError("");
      try {
        const pagina = await api.obtenerHistorialDeUso(usuario.id, POR_PAGINA, desplazamiento);
        setHistorial(pagina);
        setConsultas((previas) => (desplazamiento === 0 ? pagina.consultas : [...previas, ...pagina.consultas]));
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo cargar el historial.");
      } finally {
        setCargando(false);
      }
    },
    [usuario.id],
  );

  useEffect(() => {
    void cargar(0);
  }, [cargar]);

  const nombre = usuario.nombre ?? usuario.correo;
  const quedanMas = historial !== null && consultas.length < historial.total;

  return (
    <section
      aria-label={`Historial de uso de ${nombre}`}
      className="rounded-2xl overflow-hidden mb-4"
      style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde-marca)" }}
    >
      <div className="px-6 py-4 border-b flex items-start justify-between gap-4" style={{ borderColor: "var(--color-borde)" }}>
        <div>
          <h2 className="font-semibold" style={{ color: "var(--color-texto)" }}>Historial de uso — {nombre}</h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
            {usuario.correo} · {ETIQUETAS_ROL[usuario.rol]} · {usuario.estado}
            {historial && ` · ${formatearNumero(historial.total)} ${historial.total === 1 ? "consulta" : "consultas"}`}
          </p>
        </div>
        <button onClick={alCerrar} aria-label="Cerrar historial" className="rounded-lg p-1.5" style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--color-texto-secundario)" }}>
          <X size={16} aria-hidden="true" />
        </button>
      </div>

      {error && (
        <p className="mx-6 mt-4 rounded-xl px-4 py-3 text-sm" style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", color: "var(--color-error-texto)" }}>
          {error}
        </p>
      )}

      {historial && !historial.texto_visible && (
        <p className="px-6 py-2 text-xs" style={{ color: "var(--color-texto-tenue)" }}>
          El texto de las consultas está oculto por la configuración del sistema.
        </p>
      )}

      {historial && consultas.length === 0 && !cargando && (
        <p className="px-6 py-4 text-sm" style={{ color: "var(--color-texto-tenue)" }}>Esta cuenta todavía no ha hecho consultas.</p>
      )}

      {consultas.length > 0 && (
        <ul>
          {consultas.map((c) => (
            <li key={c.id} className="px-6 py-3 flex items-start gap-4" style={{ borderTop: "1px solid var(--color-superficie-suave)" }}>
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate" style={{ color: c.texto === null ? "var(--color-texto-tenue)" : "var(--color-texto)" }}>
                  {c.texto ?? "Texto oculto"}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "var(--color-texto-secundario)" }}>
                  {fecha(c.realizada_en)} · {c.especie ? <em>{c.especie}</em> : CELDA_VACIA}
                </p>
              </div>
              <span className="shrink-0 text-xs px-2 py-0.5 rounded-full" style={{ background: COLORES_ESTADO[c.estado].fondo, color: COLORES_ESTADO[c.estado].texto }}>
                {ETIQUETAS_ESTADO_CONSULTA[c.estado]}
              </span>
            </li>
          ))}
        </ul>
      )}

      {(quedanMas || cargando) && (
        <div className="px-6 py-3 border-t" style={{ borderColor: "var(--color-borde)" }}>
          <button
            onClick={() => void cargar(consultas.length)}
            disabled={cargando}
            className="text-xs px-3 py-1.5 rounded-lg"
            style={{ background: "var(--color-superficie-suave)", color: "var(--color-texto-cuerpo)", border: "none", cursor: cargando ? "default" : "pointer" }}
          >
            {cargando ? "Cargando…" : `Ver más (${formatearNumero(historial ? historial.total - consultas.length : 0)} restantes)`}
          </button>
        </div>
      )}
    </section>
  );
}

