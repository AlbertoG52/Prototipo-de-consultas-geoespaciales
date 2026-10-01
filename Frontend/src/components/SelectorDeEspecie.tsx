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
        style={{ background: "#ffffff", border: "1px solid #dde8df", maxWidth: 560, borderTopLeftRadius: 6 }}
      >
        <div className="px-5 py-4">
          <p className="text-sm mb-3" style={{ color: "#374a3c" }}>{mensaje}</p>
          <div className="flex flex-col gap-2">
            {candidatos.map((c) => (
              <button
                key={c.id}
                onClick={() => onElegir(c.id)}
                disabled={deshabilitado}
                className="flex items-center justify-between gap-3 text-left rounded-xl px-4 py-3 transition-all"
                style={{
                  border: "1.5px solid #c5dccb",
                  background: "#f7f8f5",
                  cursor: deshabilitado ? "default" : "pointer",
                  opacity: deshabilitado ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!deshabilitado) {
                    e.currentTarget.style.borderColor = "#2d5a3d";
                    e.currentTarget.style.background = "#e8f0eb";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "#c5dccb";
                  e.currentTarget.style.background = "#f7f8f5";
                }}
              >
                <span>
                  <span className="block text-sm font-medium" style={{ color: "#1e3d2a" }}>
                    {c.nombre_comun ?? c.nombre_cientifico}
                  </span>
                  <span className="block text-xs italic" style={{ color: "#6b8f74" }}>
                    {c.nombre_cientifico}
                  </span>
                </span>
                <span className="text-xs px-2 py-1 rounded-full shrink-0" style={{ background: "#e8f0eb", color: "#2d5a3d" }}>
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
