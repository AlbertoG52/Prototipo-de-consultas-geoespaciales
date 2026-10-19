/**
 * RR_80 — comportamiento por defecto de las respuestas (GET/PUT
 * /admin/preferencias-respuesta).
 *
 * Define si las respuestas incluyen el mapa y las fuentes para todos los que
 * no han cambiado su preferencia: usuarios, visitantes y moderadores sin
 * preferencia propia (criterio 2). Cada cambio se guarda al instante y aplica
 * desde la consulta siguiente.
 */
import { useEffect, useState } from "react";

import { IDIOMA_FECHAS } from "../../config/textos";
import * as api from "../../services/api";
import type { PreferenciasPorDefecto as Preferencias } from "../../types";
import { Interruptor } from "../Interruptor";

const OPCIONES = [
  {
    campo: "incluir_mapa",
    titulo: "Incluir mapa de distribución",
    descripcion: "El mapa geoespacial junto a la respuesta, cuando hay datos disponibles.",
  },
  {
    campo: "incluir_fuentes",
    titulo: "Mostrar fuentes de información",
    descripcion: "La lista de fuentes (GBIF, Manual de Plantas de CR) y las citas dentro de la respuesta.",
  },
] as const;

export function PreferenciasPorDefecto() {
  const [preferencias, setPreferencias] = useState<Preferencias | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    api
      .obtenerPreferenciasPorDefecto()
      .then((p) => {
        if (vigente) setPreferencias(p);
      })
      .catch((err) => {
        if (vigente) setError(err instanceof Error ? err.message : "No se pudo cargar la configuración.");
      });
    return () => {
      vigente = false;
    };
  }, []);

  async function cambiar(campo: (typeof OPCIONES)[number]["campo"]) {
    if (!preferencias) return;
    setGuardando(true);
    setError(null);
    try {
      setPreferencias(
        await api.cambiarPreferenciasPorDefecto({
          incluir_mapa: campo === "incluir_mapa" ? !preferencias.incluir_mapa : preferencias.incluir_mapa,
          incluir_fuentes: campo === "incluir_fuentes" ? !preferencias.incluir_fuentes : preferencias.incluir_fuentes,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la configuración.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section
      aria-label="Comportamiento por defecto de las respuestas"
      className="rounded-2xl p-6"
      style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}
    >
      <h2 className="font-semibold mb-1" style={{ color: "var(--color-texto)" }}>
        Comportamiento por defecto de las respuestas
      </h2>
      <p className="text-xs mb-5" style={{ color: "var(--color-texto-tenue)" }}>
        Aplica a todos los usuarios y visitantes, y a los moderadores que no han cambiado su propia
        configuración. Los cambios aplican desde la siguiente consulta.
      </p>

      {error && (
        <div
          role="alert"
          className="rounded-xl px-4 py-3 mb-4 text-sm"
          style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", color: "var(--color-error-texto)" }}
        >
          {error}
        </div>
      )}

      {!preferencias ? (
        !error && (
          <p className="text-sm" style={{ color: "var(--color-texto-tenue)" }}>
            Cargando…
          </p>
        )
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {OPCIONES.map((o) => (
              <div
                key={o.campo}
                className="flex items-center justify-between gap-4 p-4 rounded-xl"
                style={{ background: "var(--color-superficie-suave)" }}
              >
                <div>
                  <div className="text-sm font-medium" style={{ color: "var(--color-texto)" }}>
                    {o.titulo}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
                    {o.descripcion}
                  </div>
                </div>
                <Interruptor
                  activo={preferencias[o.campo]}
                  onCambiar={() => void cambiar(o.campo)}
                  etiqueta={o.titulo}
                  deshabilitado={guardando}
                />
              </div>
            ))}
          </div>
          {preferencias.actualizado_por && preferencias.actualizado_en && (
            <p className="text-xs mt-4" style={{ color: "var(--color-texto-tenue)" }}>
              Último cambio: {preferencias.actualizado_por},{" "}
              {new Date(preferencias.actualizado_en).toLocaleString(IDIOMA_FECHAS)}
            </p>
          )}
        </>
      )}
    </section>
  );
}
