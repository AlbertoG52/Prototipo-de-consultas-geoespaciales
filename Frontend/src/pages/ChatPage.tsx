/**
 * Conversación con el agente.
 *
 * Requerimientos que se implementan aquí:
 *  - RR_02 campo de texto para la consulta
 *  - RR_13 reformulación de la última consulta
 *  - RR_16 sugerencias de nombres de especie mientras se escribe (lógica en utils/sugerencias.ts)
 *
 * Lo que muestra cada mensaje vive en components/:
 *  - TarjetaRespuesta: RR_10 copiar, RR_15 descargar, RR_18 mapa o lista, RR_20 ficha
 *  - Mapa: RR_12 detalle de un punto y RR_19 filtro por elevación
 *  - SelectorDeEspecie: RR_17 selección ante varias coincidencias
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { SelectorDeEspecie } from "../components/SelectorDeEspecie";
import { TarjetaRespuesta } from "../components/TarjetaRespuesta";
import { useAuth } from "../context/AuthContext";
import { useConsultas, type Mensaje } from "../context/ConsultasContext";
import * as api from "../services/api";
import type { EspecieCandidata } from "../types";
import { incorporarNombre, nombreAInsertar, palabraEnCurso } from "../utils/sugerencias";

const CONSULTAS_DE_EJEMPLO = [
  "¿Dónde se encuentra la guaria morada?",
  "Distribución de Cedrela odorata",
  "¿Dónde crece el pejibaye?",
];

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
  const { sesion, conectando } = useAuth();
  const { mensajes, enviando, enviar } = useConsultas();
  const [entrada, setEntrada] = useState("");
  const finRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  // RR_16 — se piden sugerencias 250 ms después de la última tecla, a partir de
  // 2 letras. Si llega una respuesta de una palabra anterior, se descarta.
  const [sugerencias, setSugerencias] = useState<EspecieCandidata[]>([]);
  const fragmento = palabraEnCurso(entrada);
  useEffect(() => {
    if (fragmento.length < 2) {
      setSugerencias([]);
      return;
    }
    let vigente = true;
    const espera = setTimeout(() => {
      api
        .sugerirEspecies(fragmento)
        .then((s) => vigente && setSugerencias(s))
        .catch(() => vigente && setSugerencias([]));
    }, 250);
    return () => {
      vigente = false;
      clearTimeout(espera);
    };
  }, [fragmento]);

  // Se lleva a la vista el mensaje nuevo. Casi siempre es el último, pero al
  // elegir la especie de una consulta pendiente en una conversación reabierta
  // (RR_17) la respuesta aparece en medio, justo debajo de sus opciones.
  const idsVistos = useRef<Set<string>>(new Set());
  useEffect(() => {
    const nuevo = mensajes.find((m) => !idsVistos.current.has(m.id));
    idsVistos.current = new Set(mensajes.map((m) => m.id));
    const enMedio =
      nuevo?.clase === "respuesta" && nuevo.id !== mensajes[mensajes.length - 1]?.id;
    if (enMedio) {
      document
        .getElementById(`mensaje-${nuevo.id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      finRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [mensajes]);

  // Sin sesión todavía (el servidor está arrancando) no es lo mismo que sin
  // consultas: antes se mostraba "Agotaste tus consultas" y la caja quedaba
  // bloqueada aunque el servidor terminara de levantar.
  const sinConsultas = sesion !== null && sesion.consultas_restantes <= 0;
  const bloqueado = sesion === null || sinConsultas;

  const mandar = async (texto?: string) => {
    const valor = (texto ?? entrada).trim();
    if (!valor || enviando) return;
    setEntrada("");
    if (areaRef.current) areaRef.current.style.height = "auto";
    await enviar(valor);
  };

  // RR_13 — la última consulta que envió el usuario (también en una
  // conversación reabierta del historial).
  let ultimaConsulta: Extract<Mensaje, { clase: "consulta" }> | undefined;
  for (const m of mensajes) if (m.clase === "consulta") ultimaConsulta = m;

  /**
   * RR_13 criterios 1 y 2 — recupera el texto de la última consulta en el
   * campo de entrada para modificarlo. Al enviarlo pasa por `mandar` como
   * cualquier consulta, así que se procesa como una nueva (criterio 3).
   */
  const editarUltima = () => {
    if (!ultimaConsulta || bloqueado) return;
    const texto = ultimaConsulta.texto;
    setEntrada(texto);
    requestAnimationFrame(() => {
      const area = areaRef.current;
      if (!area) return;
      area.focus();
      area.setSelectionRange(texto.length, texto.length);
      area.style.height = "auto";
      area.style.height = `${Math.min(area.scrollHeight, 120)}px`;
    });
  };

  const alTeclear = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // RR_13 — flecha arriba con el campo vacío recupera la última consulta.
    if (e.key === "ArrowUp" && !entrada && ultimaConsulta) {
      e.preventDefault();
      editarUltima();
      return;
    }
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
          <div key={m.id} className="flex flex-col items-end">
            <div
              className="rounded-2xl px-5 py-3 text-sm font-medium max-w-sm"
              style={{ background: "#2d5a3d", color: "#ffffff", borderBottomRightRadius: 6 }}
            >
              {m.texto}
            </div>
            {/* RR_13 — solo la última consulta se puede recuperar para editarla. */}
            {m.id === ultimaConsulta?.id && !enviando && !bloqueado && (
              <button
                onClick={editarUltima}
                aria-label="Editar la última consulta"
                title="Editar y volver a enviar (↑)"
                className="flex items-center gap-1 mt-1 px-2 py-1 rounded-md text-xs"
                style={{ border: "none", background: "transparent", color: "#8aab92", cursor: "pointer" }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4 12.5-12.5z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Editar
              </button>
            )}
          </div>
        );

      case "cargando":
        return <Cargando key={m.id} />;

      case "respuesta":
        return (
          <TarjetaRespuesta
            key={m.id}
            consulta={m.consulta}
            respuesta={m.respuesta}
            onVerFicha={(especieId) => navigate(`/species/${encodeURIComponent(especieId)}`)}
          />
        );

      case "opciones":
        return (
          <SelectorDeEspecie
            key={m.id}
            mensaje={m.mensaje}
            candidatos={m.candidatos}
            deshabilitado={enviando || m.resuelta}
            // RR_17la consulta continúa con la especie elegida. Con cuenta se
            // envía también la consulta guardada, para no cobrarla dos veces.
            onElegir={(id) => void enviar(m.texto, id, m.consultaId)}
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
          {mensajes.map((m) => (
            <div key={m.id} id={`mensaje-${m.id}`}>
              {pintar(m)}
            </div>
          ))}
          <div ref={finRef} />
        </div>
      </div>

      <div className="px-8 py-5 border-t shrink-0" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        {/*
          RR_16 — mientras hay sugerencias ocupan el lugar de los ejemplos (RR_02).
          Cada una muestra el nombre común y el científico; al elegirla se
          incorpora al campo en lugar de lo que se venía escribiendo.
        */}
        <div className="flex items-center gap-2 flex-wrap mb-3">
          {sugerencias.length > 0 ? (
            <>
              <span className="text-xs" style={{ color: "#8aab92" }}>Sugerencias:</span>
              {sugerencias.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setEntrada(incorporarNombre(entrada, nombreAInsertar(s, fragmento)));
                    setSugerencias([]);
                    areaRef.current?.focus();
                  }}
                  className="text-xs px-3 py-1.5 rounded-full"
                  style={{ border: "1px solid #2d5a3d", color: "#2d5a3d", background: "#e8f0eb", cursor: "pointer" }}
                >
                  {s.nombre_comun ?? s.nombre_cientifico}
                  {s.nombre_comun && <em style={{ color: "#6b8f74" }}> · {s.nombre_cientifico}</em>}
                </button>
              ))}
            </>
          ) : (
          <>
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
          </>
          )}
        </div>

        {!sesion && (
          <div
            role="status"
            className="rounded-xl px-4 py-3 mb-3 text-sm"
            style={{ background: "#f0f5f1", border: "1px solid #dde8df", color: "#6b8f74" }}
          >
            {conectando
              ? "Conectando con el servidor… la consulta se habilita apenas responda."
              : "Cargando…"}
          </div>
        )}

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
            disabled={bloqueado}
            maxLength={500}
            aria-label="Consulta sobre flora costarricense"
            placeholder="Escribe tu consulta sobre flora costarricense..."
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm outline-none"
            style={{ color: "#1e3d2a", lineHeight: "1.5", maxHeight: 120 }}
          />
          <button
            onClick={() => void mandar()}
            disabled={!entrada.trim() || enviando || bloqueado}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all shrink-0"
            style={{
              background: entrada.trim() && !enviando && !bloqueado ? "#2d5a3d" : "#c5dccb",
              color: entrada.trim() && !enviando && !bloqueado ? "#ffffff" : "#8aab92",
              border: "none",
              cursor: entrada.trim() && !enviando && !bloqueado ? "pointer" : "default",
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
          Enter para enviar · Shift+Enter para nueva línea · ↑ para editar la última consulta
        </p>
      </div>

      <style>{`@keyframes rebote { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }`}</style>
    </>
  );
}
