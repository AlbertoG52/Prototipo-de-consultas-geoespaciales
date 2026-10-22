/**
 * RR_77 — tipos de consulta permitidos por rol (GET/PUT /admin/permisos-consulta).
 *
 * El supermoderador marca qué tipos de pregunta puede hacer el visitante, el
 * usuario y el moderador; el supermoderador siempre puede todos. Los cambios
 * se guardan con el botón y aplican desde la consulta siguiente. Quien pregunta
 * algo no permitido recibe en el chat un aviso con los tipos que sí tiene.
 */
import { useEffect, useState } from "react";

import {
  ETIQUETAS_ROL,
  ETIQUETAS_ROL_DE_CONSULTA,
  ETIQUETAS_TIPO_PREGUNTA,
  IDIOMA_FECHAS,
} from "../../config/textos";
import * as api from "../../services/api";
import type { PermisosTiposConsulta, RolDeConsulta, TipoPregunta } from "../../types";
import { Interruptor } from "../Interruptor";

/** Ejemplo de cada tipo, para que el supermoderador sepa qué está bloqueando. */
const EJEMPLOS: Record<TipoPregunta, string> = {
  distribucion: "¿Dónde crece…? Mapa, regiones, altitud",
  habitat: "¿En qué tipo de bosque vive…?",
  descripcion: "¿Cómo son las hojas de…? Familia, usos",
  general: "Solo el nombre de la especie",
};

const TIPOS = Object.keys(ETIQUETAS_TIPO_PREGUNTA) as TipoPregunta[];
const ROLES = Object.keys(ETIQUETAS_ROL_DE_CONSULTA) as RolDeConsulta[];

type Borrador = Record<RolDeConsulta, TipoPregunta[]>;

function aBorrador(permisos: PermisosTiposConsulta): Borrador {
  const borrador: Borrador = { visitante: [], usuario: [], moderador: [] };
  for (const r of permisos.roles) borrador[r.rol] = r.permitidos;
  return borrador;
}

function iguales(a: TipoPregunta[], b: TipoPregunta[]) {
  return a.length === b.length && a.every((t) => b.includes(t));
}

export function TiposDeConsultaPorRol() {
  const [permisos, setPermisos] = useState<PermisosTiposConsulta | null>(null);
  const [borrador, setBorrador] = useState<Borrador | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guardado, setGuardado] = useState(false);

  useEffect(() => {
    let vigente = true;
    api
      .obtenerPermisosDeConsulta()
      .then((p) => {
        if (!vigente) return;
        setPermisos(p);
        setBorrador(aBorrador(p));
      })
      .catch((err) => {
        if (vigente) setError(err instanceof Error ? err.message : "No se pudieron cargar los permisos.");
      });
    return () => {
      vigente = false;
    };
  }, []);

  const original = permisos ? aBorrador(permisos) : null;
  const cambiados = borrador && original ? ROLES.filter((rol) => !iguales(borrador[rol], original[rol])) : [];

  function alternar(rol: RolDeConsulta, tipo: TipoPregunta) {
    setGuardado(false);
    setBorrador((b) => {
      if (!b) return b;
      const permitidos = b[rol].includes(tipo) ? b[rol].filter((t) => t !== tipo) : [...b[rol], tipo];
      return { ...b, [rol]: permitidos };
    });
  }

  async function guardar() {
    if (!borrador || cambiados.length === 0) return;
    setGuardando(true);
    setError(null);
    try {
      const nuevos = await api.cambiarPermisosDeConsulta({
        roles: cambiados.map((rol) => ({ rol, permitidos: borrador[rol] })),
      });
      setPermisos(nuevos);
      setBorrador(aBorrador(nuevos));
      setGuardado(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron guardar los permisos.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section
      aria-label="Tipos de consulta por rol"
      className="rounded-2xl p-6"
      style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}
    >
      <h2 className="font-semibold mb-1" style={{ color: "var(--color-texto)" }}>
        Tipos de consulta por rol
      </h2>
      <p className="text-xs mb-5" style={{ color: "var(--color-texto-tenue)" }}>
        Define qué puede preguntar cada rol en el chat. Si alguien pregunta algo no permitido, se le avisa qué
        tipos tiene disponibles y no se descuenta de sus consultas. El supermoderador siempre puede hacer todas.
        Los cambios aplican desde la siguiente consulta y quedan en la auditoría.
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

      {!borrador ? (
        !error && (
          <p className="text-sm" style={{ color: "var(--color-texto-tenue)" }}>
            Cargando…
          </p>
        )
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "2px solid var(--color-superficie-suave)" }}>
                  <th className="text-left py-2 pr-4 font-medium text-xs" style={{ color: "var(--color-texto-tenue)" }}>
                    Tipo de consulta
                  </th>
                  {ROLES.map((rol) => (
                    <th key={rol} className="text-center py-2 px-3 font-medium text-xs" style={{ color: "var(--color-texto-cuerpo)" }}>
                      {ETIQUETAS_ROL_DE_CONSULTA[rol]}
                    </th>
                  ))}
                  <th className="text-center py-2 px-3 font-medium text-xs" style={{ color: "var(--color-texto-cuerpo)" }}>
                    {ETIQUETAS_ROL.supermoderador}
                  </th>
                </tr>
              </thead>
              <tbody>
                {TIPOS.map((tipo) => (
                  <tr key={tipo} style={{ borderBottom: "1px solid var(--color-superficie-suave)" }}>
                    <td className="py-3 pr-4">
                      <div className="font-medium" style={{ color: "var(--color-texto)" }}>
                        {ETIQUETAS_TIPO_PREGUNTA[tipo]}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
                        {EJEMPLOS[tipo]}
                      </div>
                    </td>
                    {ROLES.map((rol) => (
                      <td key={rol} className="py-3 px-3">
                        <div className="flex justify-center">
                          <Interruptor
                            activo={borrador[rol].includes(tipo)}
                            onCambiar={() => alternar(rol, tipo)}
                            etiqueta={`${ETIQUETAS_TIPO_PREGUNTA[tipo]} para ${ETIQUETAS_ROL_DE_CONSULTA[rol]}`}
                            deshabilitado={guardando}
                          />
                        </div>
                      </td>
                    ))}
                    <td className="py-3 px-3 text-center text-xs" style={{ color: "var(--color-texto-marca)" }}>
                      Siempre
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-3 mt-4">
            <button
              type="button"
              onClick={() => void guardar()}
              disabled={guardando || cambiados.length === 0}
              className="px-5 py-2.5 rounded-xl text-sm font-medium"
              style={{
                background: "var(--color-marca)",
                color: "var(--color-sobre-marca)",
                border: "none",
                cursor: guardando || cambiados.length === 0 ? "not-allowed" : "pointer",
                opacity: guardando || cambiados.length === 0 ? 0.6 : 1,
              }}
            >
              {guardando ? "Guardando…" : "Guardar permisos"}
            </button>
            {cambiados.length > 0 && !guardando && (
              <button
                type="button"
                onClick={() => original && setBorrador(original)}
                className="px-4 py-2.5 rounded-xl text-sm"
                style={{ background: "transparent", color: "var(--color-texto-secundario)", border: "1px solid var(--color-borde)", cursor: "pointer" }}
              >
                Descartar cambios
              </button>
            )}
            {guardado && cambiados.length === 0 && (
              <span role="status" className="text-xs" style={{ color: "var(--color-texto-marca)" }}>
                Permisos guardados.
              </span>
            )}
          </div>

          {permisos?.actualizado_por && permisos.actualizado_en && (
            <p className="text-xs mt-4" style={{ color: "var(--color-texto-tenue)" }}>
              Último cambio: {permisos.actualizado_por},{" "}
              {new Date(permisos.actualizado_en).toLocaleString(IDIOMA_FECHAS)}
            </p>
          )}
        </>
      )}
    </section>
  );
}
