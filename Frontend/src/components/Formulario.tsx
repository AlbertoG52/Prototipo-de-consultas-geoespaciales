/**
 * Piezas de formulario compartidas por las pantallas de acceso y el perfil:
 * campo de texto, aviso y botón principal. Así todos los formularios se ven
 * y se comportan igual.
 */
import { useId, type ReactNode } from "react";

const BORDE = "#c5dccb";
const BORDE_ERROR = "#fca5a5";
const BORDE_FOCO = "#2d5a3d";
const FONDO = "#f7f8f5";

/**
 * Campo con su etiqueta.
 *
 * - `error`: borde y mensaje en rojo debajo del campo.
 * - `ayuda`: texto secundario debajo del campo (se oculta si hay error).
 * - `accion`: algo a la derecha de la etiqueta, p. ej. "¿Olvidaste tu contraseña?".
 * - `children`: contenido extra bajo el campo, p. ej. el indicador de fuerza.
 */
export function CampoTexto({
  etiqueta,
  valor,
  onCambiar,
  tipo = "text",
  marcador,
  autoComplete,
  deshabilitado = false,
  error,
  ayuda,
  accion,
  children,
}: {
  etiqueta: string;
  valor: string;
  onCambiar?: (valor: string) => void;
  tipo?: "text" | "email" | "password";
  marcador?: string;
  autoComplete?: string;
  deshabilitado?: boolean;
  error?: string;
  ayuda?: string;
  accion?: ReactNode;
  children?: ReactNode;
}) {
  const id = useId();
  const borde = error ? BORDE_ERROR : BORDE;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label htmlFor={id} className="block text-sm font-medium" style={{ color: "#374a3c" }}>
          {etiqueta}
        </label>
        {accion}
      </div>
      <input
        id={id}
        type={tipo}
        value={valor}
        placeholder={marcador}
        autoComplete={autoComplete}
        disabled={deshabilitado}
        aria-invalid={error ? true : undefined}
        onChange={(e) => onCambiar?.(e.target.value)}
        className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
        style={
          deshabilitado
            ? { border: "1.5px solid #e8f0eb", background: "#f0f5f1", color: "#8aab92", cursor: "not-allowed" }
            : { border: `1.5px solid ${borde}`, background: FONDO, color: "#1e3d2a" }
        }
        onFocus={(e) => {
          if (deshabilitado) return;
          e.currentTarget.style.borderColor = BORDE_FOCO;
          e.currentTarget.style.background = "#fff";
        }}
        onBlur={(e) => {
          if (deshabilitado) return;
          e.currentTarget.style.borderColor = borde;
          e.currentTarget.style.background = FONDO;
        }}
      />
      {error ? (
        <p className="text-xs mt-1" style={{ color: "#dc2626" }}>
          {error}
        </p>
      ) : (
        ayuda && (
          <p className="text-xs mt-1" style={{ color: "#8aab92" }}>
            {ayuda}
          </p>
        )
      )}
      {children}
    </div>
  );
}

const ESTILOS_AVISO = {
  error: { background: "#fef3f2", border: "1px solid #fca5a5", color: "#991b1b" },
  exito: { background: "#e8f0eb", border: "1px solid #c5dccb", color: "#2d5a3d" },
  advertencia: { background: "#fff8e6", border: "1px solid #f3d58a", color: "#7a5a00" },
};

/**
 * Mensaje destacado. Los errores se anuncian como alerta y llevan un ícono;
 * el resto se anuncia como estado. `className` ajusta el margen según el lugar.
 */
export function Aviso({
  tipo,
  children,
  className = "mb-5",
}: {
  tipo: keyof typeof ESTILOS_AVISO;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tipo === "error" ? "alert" : "status"}
      className={`flex items-start gap-3 rounded-xl p-3.5 text-sm ${className}`}
      style={ESTILOS_AVISO[tipo]}
    >
      {tipo === "error" && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="shrink-0 mt-0.5" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
          <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      )}
      <span>{children}</span>
    </div>
  );
}

/**
 * Botón de la acción principal de un formulario.
 *
 * Ocupa todo el ancho, salvo con `bloque={false}` (perfil), donde se ajusta al
 * texto. Mientras está deshabilitado (p. ej. enviando) se muestra atenuado.
 */
export function BotonPrincipal({
  children,
  onClick,
  tipo = "button",
  deshabilitado = false,
  bloque = true,
}: {
  children: ReactNode;
  onClick?: () => void;
  tipo?: "button" | "submit";
  deshabilitado?: boolean;
  bloque?: boolean;
}) {
  return (
    <button
      type={tipo}
      onClick={onClick}
      disabled={deshabilitado}
      className={`rounded-xl text-sm font-semibold transition-all ${bloque ? "w-full py-3" : "self-start px-5 py-2.5"}`}
      style={{
        background: deshabilitado ? "#a8d4b0" : "#2d5a3d",
        color: "#ffffff",
        border: "none",
        cursor: deshabilitado ? "default" : "pointer",
      }}
    >
      {children}
    </button>
  );
}
