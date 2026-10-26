/**
 * RR_63 y RR_64 — límite de consultas de cada rol y cada cuánto se restablece.
 *
 * Cada rol se guarda por separado (PATCH /admin/roles/{rol}). El servidor
 * valida el número (RR_63 criterio 3) y que el usuario estándar quede con menos
 * consultas que el moderador y con más que un visitante (RR_62 criterio 3);
 * si no, responde el motivo y aquí se muestra. El cambio aplica a las
 * consultas siguientes de las cuentas de ese rol y queda en la auditoría.
 */
import { useState } from "react";

import { ETIQUETAS_PERIODO_CONSULTAS, ETIQUETAS_ROL, formatearNumero } from "../../config/textos";
import * as api from "../../services/api";
import type { PeriodoConsultas, RolOut } from "../../types";

const PERIODOS = Object.keys(ETIQUETAS_PERIODO_CONSULTAS) as PeriodoConsultas[];
const LIMITE_MAXIMO = 100_000; // el mismo que valida el servidor (schemas/admin.py)

const DESCRIPCIONES: Record<RolOut["nombre"], string> = {
  usuario: "Cuenta creada mediante registro público",
  moderador: "Acceso extendido con configuración adicional",
  supermoderador: "Acceso total al sistema",
};

export function LimitesPorRol({ roles, alGuardar }: { roles: RolOut[]; alGuardar: () => Promise<void> }) {
  return (
    <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
      <h2 className="font-semibold mb-1" style={{ color: "var(--color-texto)" }}>Límite de consultas por rol</h2>
      <p className="text-xs mb-5" style={{ color: "var(--color-texto-tenue)" }}>
        Cuántas consultas puede hacer cada rol y cada cuánto se restablece el contador (a las 00:00 de Costa Rica; la
        semana empieza el lunes y el mes, el día 1). El usuario estándar debe tener menos consultas que el
        moderador y más que un visitante sin cuenta; si un valor no cumple, se indica cuál sí se acepta.
      </p>
      <div className="flex flex-col gap-4">
        {roles.map((rol) => (
          <FilaRol key={`${rol.nombre}-${rol.limite_consultas}-${rol.periodo_consultas}`} rol={rol} alGuardar={alGuardar} />
        ))}
      </div>
    </div>
  );
}

function FilaRol({ rol, alGuardar }: { rol: RolOut; alGuardar: () => Promise<void> }) {
  const [limite, setLimite] = useState(String(rol.limite_consultas));
  const [periodo, setPeriodo] = useState<PeriodoConsultas>(rol.periodo_consultas);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "error" | "ok"; texto: string } | null>(null);

  const numero = Number(limite);
  const valido = limite.trim() !== "" && Number.isInteger(numero) && numero >= 1 && numero <= LIMITE_MAXIMO;
  const cambiado = numero !== rol.limite_consultas || periodo !== rol.periodo_consultas;

  const guardar = async () => {
    if (!valido || !cambiado || guardando) return;
    setGuardando(true);
    setMensaje(null);
    try {
      await api.configurarLimite(rol.nombre, numero, periodo);
      await alGuardar(); // recarga roles y auditoría; esta fila se vuelve a montar con lo guardado
    } catch (err) {
      setMensaje({ tipo: "error", texto: err instanceof Error ? err.message : "No se pudo guardar el límite." });
      setGuardando(false);
    }
  };

  const id = `limite-${rol.nombre}`;
  return (
    <div className="p-4 rounded-xl" style={{ background: "var(--color-superficie-suave)" }}>
      {/* Los controles bajan a otra línea cuando no caben junto al nombre. Depende del
          espacio de la tarjeta, no del ancho de la ventana: el panel tiene dos barras
          laterales, así que una ventana mediana deja poco espacio. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="flex-1 basis-48 min-w-48">
          <label htmlFor={id} className="text-sm font-medium" style={{ color: "var(--color-texto)" }}>
            {ETIQUETAS_ROL[rol.nombre]}
          </label>
          <div className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
            {DESCRIPCIONES[rol.nombre]}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap max-w-full">
          <input
            id={id}
            type="number"
            inputMode="numeric"
            min={1}
            max={LIMITE_MAXIMO}
            step={1}
            value={limite}
            onChange={(e) => {
              setLimite(e.target.value);
              setMensaje(null);
            }}
            aria-invalid={!valido}
            className="rounded-xl px-3 py-2 text-sm text-center outline-none font-medium"
            style={{
              width: 96,
              border: `1.5px solid ${valido ? "var(--color-borde-fuerte)" : "var(--color-error-borde)"}`,
              background: "var(--color-superficie)",
              color: "var(--color-texto)",
            }}
          />
          <span className="text-xs" style={{ color: "var(--color-texto-secundario)" }}>consultas</span>
          <select
            value={periodo}
            onChange={(e) => {
              setPeriodo(e.target.value as PeriodoConsultas);
              setMensaje(null);
            }}
            aria-label={`Periodo del límite de ${ETIQUETAS_ROL[rol.nombre]}`}
            className="rounded-xl px-3 py-2 text-sm outline-none"
            style={{ border: "1.5px solid var(--color-borde-fuerte)", background: "var(--color-superficie)", color: "var(--color-texto)" }}
          >
            {PERIODOS.map((p) => (
              <option key={p} value={p}>{ETIQUETAS_PERIODO_CONSULTAS[p]}</option>
            ))}
          </select>
          <button
            onClick={() => void guardar()}
            disabled={!valido || !cambiado || guardando}
            className="px-4 py-2 rounded-xl text-sm font-medium"
            style={{
              background: "var(--color-marca)",
              color: "var(--color-sobre-marca)",
              border: "none",
              cursor: !valido || !cambiado || guardando ? "not-allowed" : "pointer",
              opacity: !valido || !cambiado || guardando ? 0.5 : 1,
            }}
          >
            {guardando ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </div>
      {!valido && (
        <p className="text-xs mt-2" style={{ color: "var(--color-error-texto)" }}>
          Escribe un número entero entre 1 y {formatearNumero(LIMITE_MAXIMO)}.
        </p>
      )}
      {mensaje && (
        <p role="alert" className="text-xs mt-2" style={{ color: mensaje.tipo === "error" ? "var(--color-error-texto)" : "var(--color-texto-marca)" }}>
          {mensaje.texto}
        </p>
      )}
    </div>
  );
}
