/** RR_17 — lista de especies que coinciden, para que el usuario elija. */
export function SelectorDeEspecie({
  mensaje,
  candidatos,
  onElegir,
  deshabilitado,
}: {
  mensaje: string;
  candidatos: { id: string; nombre_comun: string | null; nombre_cientifico: string; familia: string }[];
  onElegir: (id: string) => void;
  deshabilitado: boolean;
}) {
  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl overflow-hidden"
        style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)", maxWidth: 560, borderTopLeftRadius: 6 }}
      >
        <div className="px-5 py-4">
          <p className="text-sm mb-3" style={{ color: "var(--color-texto-cuerpo)" }}>{mensaje}</p>
          <div className="flex flex-col gap-2">
            {candidatos.map((c) => (
              <button
                key={c.id}
                onClick={() => onElegir(c.id)}
                disabled={deshabilitado}
                className="flex items-center justify-between gap-3 text-left rounded-xl px-4 py-3 transition-all"
                style={{
                  border: "1.5px solid var(--color-borde-fuerte)",
                  background: "var(--color-fondo)",
                  cursor: deshabilitado ? "default" : "pointer",
                  opacity: deshabilitado ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!deshabilitado) {
                    e.currentTarget.style.borderColor = "var(--color-borde-marca)";
                    e.currentTarget.style.background = "var(--color-superficie-marca)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-borde-fuerte)";
                  e.currentTarget.style.background = "var(--color-fondo)";
                }}
              >
                <span>
                  <span className="block text-sm font-medium italic" style={{ color: "var(--color-texto)" }}>
                    {c.nombre_cientifico}
                  </span>
                  {c.nombre_comun && (
                    <span className="block text-xs" style={{ color: "var(--color-texto-secundario)" }}>
                      {c.nombre_comun}
                    </span>
                  )}
                </span>
                <span className="text-xs px-2 py-1 rounded-full shrink-0" style={{ background: "var(--color-superficie-marca)", color: "var(--color-texto-marca)" }}>
                  {c.familia}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
