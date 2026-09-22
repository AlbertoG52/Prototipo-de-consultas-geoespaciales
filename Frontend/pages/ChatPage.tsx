/**
 * Conversación con el agente.
 *
 * Requerimientos que se implementan aquí:
 *  - RR_02 campo de texto para la consulta
 *  - RR_10 copiar la respuesta
 *  - RR_17 selección de especie ante múltiples coincidencias
 *  - RR_18 alternancia entre mapa y lista de registros
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { useAuth } from "../context/AuthContext";
import { useConsultas, type Mensaje } from "../context/ConsultasContext";
import type { RegistroPresencia, RespuestaConsulta } from "../types";

const CONSULTAS_DE_EJEMPLO = [
  "¿Dónde se encuentra la guaria morada?",
  "Distribución de Cedrela odorata",
  "¿Dónde crece el pejibaye?",
];

/**
 * Mapa de distribución.
 *
 * El mapa geoespacial real lo genera CR-BioLM y es parte del módulo 3, que no
 * pertenece a este sprint. Esto dibuja los registros que sí tenemos sobre una
 * silueta del país, proyectando latitud y longitud a coordenadas del SVG, para
 * que la alternancia de RR_18 tenga las dos vistas que compara.
 */
function MapaDistribucion({ registros }: { registros: RegistroPresencia[] }) {
  // Recuadro aproximado de Costa Rica.
  const LON_MIN = -86.0;
  const LON_MAX = -82.5;
  const LAT_MIN = 8.0;
  const LAT_MAX = 11.3;

  const aX = (lon: number) => 60 + ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * 220;
  const aY = (lat: number) => 150 - ((lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * 100;

  return (
    <svg viewBox="0 0 340 180" className="w-full h-full" style={{ background: "#e8f0e8" }} role="img" aria-label="Mapa de distribución en Costa Rica">
      <path
        d="M60,90 Q80,60 120,55 Q160,50 200,60 Q230,65 250,80 Q270,90 260,110 Q250,130 220,140 Q180,150 140,148 Q100,145 75,130 Q50,115 60,90 Z"
        fill="#c8dfc0"
        stroke="#9ab89a"
        strokeWidth="1.5"
      />
      {registros.map((r, i) => (
        <circle
          key={i}
          cx={aX(r.longitud)}
          cy={aY(r.latitud)}
          r={4.5}
          fill="#5b4fcf"
          opacity={0.85}
        >
          <title>{`${r.localidad} — ${r.fecha}`}</title>
        </circle>
      ))}
      <circle cx="100" cy="160" r="5" fill="#5b4fcf" opacity="0.85" />
      <text x="110" y="164" fontSize="9" fill="#555" fontFamily="Inter, sans-serif">
        Registros de presencia ({registros.length})
      </text>
      <line x1="240" y1="162" x2="290" y2="162" stroke="#666" strokeWidth="1.5" />
      <line x1="240" y1="158" x2="240" y2="162" stroke="#666" strokeWidth="1.5" />
      <line x1="290" y1="158" x2="290" y2="162" stroke="#666" strokeWidth="1.5" />
      <text x="257" y="172" fontSize="8" fill="#666" fontFamily="Inter, sans-serif">
        50 km
      </text>
    </svg>
  );
}

function TarjetaRespuesta({
  respuesta,
  onVerFicha,
}: {
  respuesta: RespuestaConsulta;
  onVerFicha: (nombre: string) => void;
}) {
  const [copiado, setCopiado] = useState(false);
  // RR_18 — el usuario alterna entre las dos vistas de los mismos registros.
  const [vista, setVista] = useState<"mapa" | "lista">("mapa");

  /** RR_10 — copiar el texto de la respuesta y confirmarlo visualmente. */
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(respuesta.texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      /* el navegador puede bloquear el portapapeles sin HTTPS */
    }
  };

  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl overflow-hidden w-full"
        style={{ background: "#ffffff", border: "1px solid #dde8df", maxWidth: 560, borderTopLeftRadius: 6 }}
      >
        <div className="px-6 py-5" style={{ background: "#2d5a3d" }}>
          <div
            className="text-xs font-medium mb-1"
            style={{ color: "#a8d4b0", letterSpacing: "0.12em" }}
          >
            {respuesta.especie.familia}
          </div>
          <div className="text-2xl font-bold" style={{ color: "#ffffff", fontFamily: "'Lora', serif" }}>
            {respuesta.especie.nombre_comun ?? respuesta.especie.nombre_cientifico}
          </div>
          <div className="text-sm italic mt-0.5" style={{ color: "#c5e8cc" }}>
            {respuesta.especie.nombre_cientifico}
          </div>
          <div className="flex items-center gap-4 mt-3 flex-wrap">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{ background: "rgba(255,255,255,0.15)", color: "#e8f0eb" }}
            >
              {respuesta.total_registros} registros
            </span>
            {respuesta.elevacion && (
              <span
                className="text-xs px-2 py-1 rounded-full"
                style={{ background: "rgba(255,255,255,0.15)", color: "#e8f0eb" }}
              >
                {respuesta.elevacion}
              </span>
            )}
          </div>
        </div>

        <div className="px-6 py-5">
          <p className="text-sm leading-relaxed" style={{ color: "#374a3c" }}>
            {respuesta.texto}
          </p>

          {respuesta.registros.length > 0 && (
            <>
              {/* RR_18 cambiar entre la vista de mapa y la de lista. */}
              <div
                className="flex gap-1 mt-4 mb-3 p-1 rounded-xl"
                style={{ background: "#f0f5f1", width: "fit-content" }}
                role="group"
                aria-label="Vista de los registros"
              >
                {(["mapa", "lista"] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setVista(v)}
                    aria-pressed={vista === v}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: vista === v ? "#2d5a3d" : "transparent",
                      color: vista === v ? "#fff" : "#6b8f74",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    {v === "mapa" ? "Mapa" : "Lista de registros"}
                  </button>
                ))}
              </div>

              {/*
                RR_18 ambas vistas muestran la misma especie:
                las dos leen `respuesta.registros`, no dos fuentes distintas.
              */}
              {vista === "mapa" ? (
                <>
                  <div className="flex items-center gap-1.5 mb-2">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#2d5a3d" />
                      <circle cx="12" cy="9" r="2.5" fill="white" />
                    </svg>
                    <span className="text-sm font-medium" style={{ color: "#2d5a3d" }}>
                      Distribución en Costa Rica
                    </span>
                  </div>
                  <div className="rounded-xl overflow-hidden" style={{ height: 170, border: "1px solid #dde8df" }}>
                    <MapaDistribucion registros={respuesta.registros} />
                  </div>
                </>
              ) : (
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #dde8df" }}>
                  <table className="w-full text-xs">
                    <thead style={{ background: "#f0f5f1" }}>
                      <tr>
                        {["Localidad", "Fecha", "Coordenadas", "Elevación"].map((h) => (
                          <th key={h} className="px-3 py-2 text-left font-medium" style={{ color: "#374a3c" }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {respuesta.registros.map((r, i) => (
                        <tr key={i} style={{ borderTop: "1px solid #dde8df" }}>
                          <td className="px-3 py-2" style={{ color: "#374a3c" }}>{r.localidad}</td>
                          <td className="px-3 py-2" style={{ color: "#6b8f74" }}>{r.fecha}</td>
                          <td className="px-3 py-2" style={{ color: "#6b8f74", fontFamily: "monospace" }}>
                            {r.latitud.toFixed(4)}, {r.longitud.toFixed(4)}
                          </td>
                          <td className="px-3 py-2" style={{ color: "#6b8f74" }}>
                            {r.elevacion_m !== null ? `${r.elevacion_m} m` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          <div className="mt-4 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm" style={{ color: "#6b8f74" }}>Fuentes:</span>
              {respuesta.fuentes.map((f) => (
                <span
                  key={f}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{ border: "1px solid #c5dccb", color: "#2d5a3d", background: "#f0f5f1", fontWeight: 500 }}
                >
                  {f}
                </span>
              ))}
            </div>
            <div className="flex items-center gap-1">
              {/* RR_10 — botón visible, y confirmación visual al copiar. */}
              <button
                onClick={copiar}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{
                  background: copiado ? "#e8f0eb" : "transparent",
                  color: copiado ? "#2d5a3d" : "#8aab92",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" strokeWidth="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke="currentColor" strokeWidth="2" />
                </svg>
                {copiado ? "Copiado" : "Copiar"}
              </button>
              <button
                onClick={() => onVerFicha(respuesta.especie.nombre_cientifico)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all"
                style={{ background: "transparent", color: "#8aab92", border: "none", cursor: "pointer" }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Ficha completa
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** RR_17 — lista de especies que coinciden, para que el usuario elija. */
function SelectorDeEspecie({
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

function Cargando() {
  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl px-5 py-4"
        style={{ background: "#ffffff", border: "1px solid #dde8df", borderTopLeftRadius: 6 }}
      >
        <div className="flex items-center gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="rounded-full"
              style={{ width: 8, height: 8, background: "#2d5a3d", animation: `rebote 1.2s ${i * 0.2}s infinite`, opacity: 0.7 }}
            />
          ))}
          <span className="text-sm ml-1" style={{ color: "#6b8f74" }}>
            Procesando consulta...
          </span>
        </div>
      </div>
    </div>
  );
}

export function ChatPage() {
  const navigate = useNavigate();
  const { sesion } = useAuth();
  const { mensajes, enviando, enviar } = useConsultas();
  const [entrada, setEntrada] = useState("");
  const finRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  const sinConsultas = (sesion?.consultas_restantes ?? 0) <= 0;

  const mandar = async (texto?: string) => {
    const valor = (texto ?? entrada).trim();
    if (!valor || enviando) return;
    setEntrada("");
    if (areaRef.current) areaRef.current.style.height = "auto";
    await enviar(valor);
  };

  const alTeclear = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void mandar();
    }
  };

  const alCambiar = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEntrada(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const pintar = (m: Mensaje) => {
    switch (m.clase) {
      case "consulta":
        return (
          <div key={m.id} className="flex justify-end">
            <div
              className="rounded-2xl px-5 py-3 text-sm font-medium max-w-sm"
              style={{ background: "#2d5a3d", color: "#ffffff", borderBottomRightRadius: 6 }}
            >
              {m.texto}
            </div>
          </div>
        );

      case "cargando":
        return <Cargando key={m.id} />;

      case "respuesta":
        return (
          <TarjetaRespuesta
            key={m.id}
            respuesta={m.respuesta}
            onVerFicha={(nombre) => navigate(`/species/${encodeURIComponent(nombre)}`)}
          />
        );

      case "opciones":
        return (
          <SelectorDeEspecie
            key={m.id}
            mensaje={m.mensaje}
            candidatos={m.candidatos}
            deshabilitado={enviando}
            // RR_17la consulta continúa con la especie elegida.
            onElegir={(id) => void enviar(m.texto, id)}
          />
        );

      case "aviso":
        return (
          <div key={m.id} className="flex justify-start">
            <div
              className="rounded-2xl px-5 py-4 max-w-md"
              style={{ background: "#ffffff", border: "1px solid #dde8df", borderTopLeftRadius: 6 }}
            >
              <p className="text-sm" style={{ color: "#6b8f74" }}>{m.mensaje}</p>
            </div>
          </div>
        );

      case "error":
        return (
          <div key={m.id} className="flex justify-start">
            <div
              className="rounded-2xl overflow-hidden max-w-sm"
              style={{ background: "#fef3f2", border: "1px solid #fca5a5", borderTopLeftRadius: 6 }}
            >
              <div className="px-5 py-4">
                <div className="flex items-center gap-2 mb-2">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" stroke="#dc2626" strokeWidth="2" />
                    <path d="M12 8v4M12 16h.01" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                  <span className="text-sm font-medium" style={{ color: "#dc2626" }}>
                    No se pudo completar la consulta
                  </span>
                </div>
                <p className="text-sm" style={{ color: "#991b1b" }}>{m.mensaje}</p>
                <button
                  onClick={() => void mandar(m.textoOriginal)}
                  className="text-xs mt-3 font-medium"
                  style={{ color: "#dc2626", border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
                >
                  Reintentar consulta
                </button>
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <>
      <div className="px-8 py-5 border-b shrink-0" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        <h1 className="text-xl font-semibold" style={{ color: "#1e3d2a" }}>
          Flora de Costa Rica
        </h1>
        <p className="text-sm" style={{ color: "#6b8f74" }}>
          Consulta sobre especies, distribución y ecología vegetal
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6" style={{ background: "#f7f8f5" }}>
        <div className="flex flex-col gap-6 max-w-2xl">
          {mensajes.length === 0 && (
            <div className="rounded-2xl px-6 py-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <h2 className="text-base font-semibold mb-1" style={{ color: "#1e3d2a" }}>
                Pregunta por una planta de Costa Rica
              </h2>
              <p className="text-sm" style={{ color: "#6b8f74" }}>
                Escribe abajo el nombre común o científico de una especie y te muestro dónde se
                ha registrado y qué se sabe de ella.
              </p>
            </div>
          )}
          {mensajes.map(pintar)}
          <div ref={finRef} />
        </div>
      </div>

      <div className="px-8 py-5 border-t shrink-0" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        {/* RR_02  ejemplos orientativos de lo que se puede preguntar. */}
        <div className="flex items-center gap-2 flex-wrap mb-3">
          <span className="text-xs" style={{ color: "#8aab92" }}>Ejemplos:</span>
          {CONSULTAS_DE_EJEMPLO.map((ej) => (
            <button
              key={ej}
              onClick={() => {
                setEntrada(ej);
                areaRef.current?.focus();
              }}
              className="text-xs px-3 py-1.5 rounded-full transition-all"
              style={{ border: "1px solid #c5dccb", color: "#2d5a3d", background: "transparent", cursor: "pointer" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#e8f0eb";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              {ej}
            </button>
          ))}
        </div>

        {sinConsultas && (
          <div
            className="rounded-xl px-4 py-3 mb-3 text-sm"
            style={{ background: "#fef3f2", border: "1px solid #fca5a5", color: "#991b1b" }}
          >
            Agotaste tus consultas de hoy.{" "}
            {sesion?.tipo === "anonimo" && (
              <button
                onClick={() => navigate("/register")}
                className="font-medium underline"
                style={{ color: "#991b1b", border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
              >
                Crea una cuenta para obtener más.
              </button>
            )}
          </div>
        )}

        {/* RR_02 — campo de texto libre en español para la consulta. */}
        <div
          className="flex items-end gap-3 rounded-2xl px-4 py-3"
          style={{ border: "1.5px solid #c5dccb", background: "#f7f8f5" }}
          onFocusCapture={(e) => {
            e.currentTarget.style.borderColor = "#2d5a3d";
          }}
          onBlurCapture={(e) => {
            e.currentTarget.style.borderColor = "#c5dccb";
          }}
        >
          <textarea
            ref={areaRef}
            value={entrada}
            onChange={alCambiar}
            onKeyDown={alTeclear}
            disabled={sinConsultas}
            maxLength={500}
            aria-label="Consulta sobre flora costarricense"
            placeholder="Escribe tu consulta sobre flora costarricense..."
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm outline-none"
            style={{ color: "#1e3d2a", lineHeight: "1.5", maxHeight: 120 }}
          />
          <button
            onClick={() => void mandar()}
            disabled={!entrada.trim() || enviando || sinConsultas}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all shrink-0"
            style={{
              background: entrada.trim() && !enviando && !sinConsultas ? "#2d5a3d" : "#c5dccb",
              color: entrada.trim() && !enviando && !sinConsultas ? "#ffffff" : "#8aab92",
              border: "none",
              cursor: entrada.trim() && !enviando && !sinConsultas ? "pointer" : "default",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Enviar
          </button>
        </div>
        <p className="text-center text-xs mt-2" style={{ color: "#a0b8a8" }}>
          Enter para enviar · Shift+Enter para nueva línea
        </p>
      </div>

      <style>{`@keyframes rebote { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }`}</style>
    </>
  );
}
