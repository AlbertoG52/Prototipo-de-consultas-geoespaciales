/**
 * Interruptor de encendido y apagado (role="switch").
 *
 * Lo usan las preferencias del perfil (apariencia, RR_67 y RR_68), el
 * comportamiento por defecto de las respuestas en administración (RR_80) y
 * los tipos de consulta por rol (RR_77).
 */
export function Interruptor({
  activo,
  onCambiar,
  etiqueta,
  deshabilitado = false,
}: {
  activo: boolean;
  onCambiar: () => void;
  etiqueta: string;
  deshabilitado?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      onClick={onCambiar}
      disabled={deshabilitado}
      className="relative rounded-full transition-all"
      style={{
        width: 44,
        height: 24,
        background: activo ? "var(--color-marca)" : "var(--color-borde-fuerte)",
        border: "none",
        cursor: deshabilitado ? "not-allowed" : "pointer",
        opacity: deshabilitado ? 0.6 : 1,
        flexShrink: 0,
      }}
    >
      <span
        className="absolute rounded-full transition-all"
        style={{
          width: 18,
          height: 18,
          background: "var(--color-sobre-marca)",
          top: 3,
          left: activo ? 23 : 3,
          boxShadow: "var(--sombra-interruptor)",
        }}
      />
    </button>
  );
}
