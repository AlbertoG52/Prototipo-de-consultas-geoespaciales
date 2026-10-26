/**
 * Conversación con el agente.
 *
 * Requerimientos que se implementan aquí:
 *  - RR_02 campo de texto para la consulta
 *  - RR_13 reformulación de la última consulta
 *  - RR_16 sugerencias de nombres de especie mientras se escribe (lógica en utils/sugerencias.ts)
 *  - RR_34 límite de caracteres de la consulta (contador y aviso)
 *  - RR_22, RR_32, RR_37, RR_40 orientación con ejemplos cuando el mensaje no es una consulta
 *
 * Lo que muestra cada mensaje vive en components/:
 *  - TarjetaRespuesta: RR_10 copiar, RR_15 descargar, RR_18 mapa o lista, RR_20 ficha,
 *    RR_12 detalle de un registro y RR_19 filtro por elevación (en la lista)
 *  - Mapa: RR_46 mapa de distribución de CR-BioLM (PNG), DetallePunto y FiltroElevacion
 *  - SelectorDeEspecie: RR_17 selección ante varias coincidencias
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { CircleAlert, PenLine, Send } from "lucide-react";
import { SelectorDeEspecie } from "../components/SelectorDeEspecie";
import { TarjetaRespuesta } from "../components/TarjetaRespuesta";
import { useAuth } from "../context/AuthContext";
import { useConsultas, type Mensaje } from "../context/ConsultasContext";
import * as api from "../services/api";
import type { EspecieCandidata, Sesion } from "../types";
import { formatearReinicio, largoConsulta, PERIODO_ACTUAL, textoConsultaLarga } from "../config/textos";
import { incorporarNombre, nombreAInsertar, palabraEnCurso } from "../utils/sugerencias";

// RR_34 — el contador de caracteres aparece desde el 80 % del límite.
const PROPORCION_AVISO_LIMITE = 0.8;

const CONSULTAS_DE_EJEMPLO = [
  "¿Dónde crece Quercus costaricensis?",
  "Distribución de Cedrela tonduzii",
  "¿Dónde se encuentra Bactris gasipaes?",
];

const ATAJOS = "Enter para enviar · Shift+Enter para nueva línea · ↑ para editar la última consulta";

/** Una consulta de ejemplo: al tocarla se copia al campo de texto para enviarla o editarla. */
function BotonDeEjemplo({ texto, onUsar }: { texto: string; onUsar: (texto: string) => void }) {
  return (
    <button
      onClick={() => onUsar(texto)}
      className="text-xs px-3 py-1.5 rounded-full transition-all"
      style={{ border: "1px solid var(--color-borde-fuerte)", color: "var(--color-texto-marca)", background: "transparent", cursor: "pointer" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--color-superficie-marca)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      {texto}
    </button>
  );
}

function Cargando() {
  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl px-5 py-4"
        style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)", borderTopLeftRadius: 6 }}
      >
        <div className="flex items-center gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="rounded-full"
              style={{ width: 8, height: 8, background: "var(--color-marca)", animation: `rebote 1.2s ${i * 0.2}s infinite`, opacity: 0.7 }}
            />
          ))}
          <span className="text-sm ml-1" style={{ color: "var(--color-texto-secundario)" }}>
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
  const areaConsultaRef = useRef<HTMLDivElement>(null);
  const contenidoConsultaRef = useRef<HTMLDivElement>(null);

  // Altura natural del área de la consulta -> --alto-pie-chat, para alinearla
  // con el pie de la barra lateral (ver pages/Root.tsx).
  useEffect(() => {
    const area = areaConsultaRef.current;
    const contenido = contenidoConsultaRef.current;
    if (!area || !contenido) return;
    const raiz = document.documentElement.style;
    const medir = () => {
      const estilo = getComputedStyle(area);
      const extra = ["paddingTop", "paddingBottom", "borderTopWidth"] as const;
      const alto = contenido.offsetHeight + extra.reduce((suma, k) => suma + parseFloat(estilo[k]), 0);
      raiz.setProperty("--alto-pie-chat", `${Math.round(alto)}px`);
    };
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(contenido);
    return () => {
      observador.disconnect();
      raiz.removeProperty("--alto-pie-chat");
    };
  }, []);

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

  // RR_34 — el límite lo define el servidor. No se corta lo que se escribe o se
  // pega: se muestra cuánto sobra y no se deja enviar hasta acortarlo.
  const limite = sesion?.longitud_maxima_consulta;
  const largo = largoConsulta(entrada);
  const excede = limite !== undefined && largo > limite;
  const cercaDelLimite = limite !== undefined && largo >= limite * PROPORCION_AVISO_LIMITE;
  const puedeEnviar = entrada.trim() !== "" && !excede && !enviando && !bloqueado;

  const mandar = async (texto?: string) => {
    const valor = (texto ?? entrada).trim();
    if (!valor || enviando) return;
    if (limite !== undefined && largoConsulta(valor) > limite) return;
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

  /** Un ejemplo pasa al campo de texto; la persona decide si lo envía. */
  const usarEjemplo = (texto: string) => {
    setEntrada(texto);
    areaRef.current?.focus();
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
              style={{ background: "var(--color-marca)", color: "var(--color-sobre-marca)", borderBottomRightRadius: 6 }}
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
                style={{ border: "none", background: "transparent", color: "var(--color-texto-tenue)", cursor: "pointer" }}
              >
                <PenLine size={12} />
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
              style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)", borderTopLeftRadius: 6 }}
            >
              <p className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>{m.mensaje}</p>
            </div>
          </div>
        );

      // RR_22, RR_32, RR_37, RR_40 — el mensaje puede traer saltos de línea (la ayuda).
      case "orientacion":
        return (
          <div key={m.id} className="flex justify-start">
            <div
              className="rounded-2xl px-5 py-4 max-w-md"
              style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)", borderTopLeftRadius: 6 }}
            >
              <p className="text-sm" style={{ color: "var(--color-texto-secundario)", whiteSpace: "pre-line" }}>
                {m.mensaje}
              </p>
              {m.ejemplos.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>Prueba con:</span>
                  {m.ejemplos.map((ej) => (
                    <BotonDeEjemplo key={ej} texto={ej} onUsar={usarEjemplo} />
                  ))}
                </div>
              )}
            </div>
          </div>
        );

      case "error":
        return (
          <div key={m.id} className="flex justify-start">
            <div
              className="rounded-2xl overflow-hidden max-w-sm"
              style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", borderTopLeftRadius: 6 }}
            >
              <div className="px-5 py-4">
                <div className="flex items-center gap-2 mb-2">
                  <CircleAlert size={16} style={{ color: "var(--color-error)" }} />
                  <span className="text-sm font-medium" style={{ color: "var(--color-error)" }}>
                    No se pudo completar la consulta
                  </span>
                </div>
                <p className="text-sm" style={{ color: "var(--color-error-texto)" }}>{m.mensaje}</p>
                <button
                  onClick={() => void mandar(m.textoOriginal)}
                  className="text-xs mt-3 font-medium"
                  style={{ color: "var(--color-error)", border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
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
      <div className="px-4 md:px-8 py-4 md:py-5 border-b shrink-0" style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}>
        <h1 className="text-lg md:text-xl font-semibold" style={{ color: "var(--color-texto)" }}>
          Flora de Costa Rica
        </h1>
        <p className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>
          Consulta sobre especies, distribución y ecología vegetal
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6" style={{ background: "var(--color-fondo)" }}>
        <div className="flex flex-col gap-6 w-full max-w-4xl mx-auto">
          {mensajes.length === 0 && (
            <div className="rounded-2xl px-6 py-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
              <h2 className="text-base font-semibold mb-1" style={{ color: "var(--color-texto)" }}>
                Pregunta por una planta de Costa Rica
              </h2>
              <p className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>
                Escribe abajo el nombre común o científico de una especie y te muestro dónde se
                ha registrado y qué se sabe de ella.
              </p>
              {/* RR_02 — ejemplos de consulta; solo con la conversación vacía. */}
              <div className="flex items-center gap-2 flex-wrap mt-4">
                <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>Prueba con:</span>
                {CONSULTAS_DE_EJEMPLO.map((ej) => (
                  <BotonDeEjemplo key={ej} texto={ej} onUsar={usarEjemplo} />
                ))}
              </div>
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

      {/*
        La conversación y esta área van en una columna centrada de max-w-4xl.
        En pantallas grandes esta área y el pie de la barra lateral usan la misma
        altura mínima, para que sus líneas divisorias queden alineadas (ver
        pages/Root.tsx).
      */}
      <div
        ref={areaConsultaRef}
        className="px-4 md:px-8 py-3 md:py-4 border-t shrink-0 flex flex-col justify-center md:min-h-[max(var(--alto-pie-lateral,0px),var(--alto-pie-chat,0px))]"
        style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}
      >
        <div ref={contenidoConsultaRef} className="w-full max-w-4xl mx-auto">
          {/*
            RR_16 — sugerencias de nombres mientras se escribe; solo aparecen
            cuando hay. Cada una muestra el nombre científico y el común; al
            elegirla se incorpora al campo en lugar de lo que se venía escribiendo.
          */}
          {sugerencias.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap mb-3">
              <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>Sugerencias:</span>
              {sugerencias.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setEntrada(incorporarNombre(entrada, nombreAInsertar(s, fragmento)));
                    setSugerencias([]);
                    areaRef.current?.focus();
                  }}
                  className="text-xs px-3 py-1.5 rounded-full"
                  style={{ border: "1px solid var(--color-borde-marca)", color: "var(--color-texto-marca)", background: "var(--color-superficie-marca)", cursor: "pointer" }}
                >
                  <em>{s.nombre_cientifico}</em>
                  {s.nombre_comun && <span style={{ color: "var(--color-texto-secundario)" }}> · {s.nombre_comun}</span>}
                </button>
              ))}
            </div>
          )}

          {!sesion && (
            <div
              role="status"
              className="rounded-xl px-4 py-3 mb-3 text-sm"
              style={{ background: "var(--color-superficie-suave)", border: "1px solid var(--color-borde)", color: "var(--color-texto-secundario)" }}
            >
              {conectando
                ? "Conectando con el servidor… la consulta se habilita apenas responda."
                : "Cargando…"}
            </div>
          )}

          {sinConsultas && (
            <div
              className="rounded-xl px-4 py-3 mb-3 text-sm"
              style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", color: "var(--color-error-texto)" }}
            >
              {/* RR_65 — antes de enviar: qué periodo se agotó y cuándo se restablece. */}
              {sesion && avisoSinConsultas(sesion)}{" "}
              {sesion?.tipo === "anonimo" && (
                <button
                  onClick={() => navigate("/register")}
                  className="font-medium underline"
                  style={{ color: "var(--color-error-texto)", border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
                >
                  Crea una cuenta para obtener más.
                </button>
              )}
            </div>
          )}

          {/* RR_02 — campo de texto libre en español para la consulta. */}
          <div
            className="flex items-end gap-3 rounded-2xl px-4 py-2"
            style={{ border: "1.5px solid var(--color-borde-fuerte)", background: "var(--color-fondo)" }}
            onFocusCapture={(e) => {
              e.currentTarget.style.borderColor = "var(--color-borde-marca)";
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = "var(--color-borde-fuerte)";
            }}
          >
            <textarea
              ref={areaRef}
              value={entrada}
              onChange={alCambiar}
              onKeyDown={alTeclear}
              disabled={bloqueado}
              aria-label="Consulta sobre flora costarricense"
              aria-invalid={excede}
              aria-describedby="limite-consulta atajos-consulta"
              title={ATAJOS}
              placeholder="Escribe tu consulta sobre flora costarricense..."
              rows={1}
              className="flex-1 min-w-0 resize-none bg-transparent text-sm outline-none self-center"
              style={{ color: "var(--color-texto)", lineHeight: "1.5", maxHeight: 120 }}
            />
            <button
              onClick={() => void mandar()}
              disabled={!puedeEnviar}
              title={ATAJOS}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-sm font-medium transition-all shrink-0"
              style={{
                background: puedeEnviar ? "var(--color-marca)" : "var(--color-borde-fuerte)",
                color: puedeEnviar ? "var(--color-sobre-marca)" : "var(--color-texto-tenue)",
                border: "none",
                cursor: puedeEnviar ? "pointer" : "default",
              }}
            >
              <Send size={14} />
              Enviar
            </button>
          </div>
          {/* RR_34 criterios 2 y 3 — el contador aparece cerca del límite y avisa al pasarlo. */}
          <div id="limite-consulta" aria-live="polite">
            {limite !== undefined && (excede || cercaDelLimite) && (
              <p
                className="flex items-center justify-end gap-1.5 text-xs mt-2"
                style={{ color: excede ? "var(--color-error-texto)" : "var(--color-texto-tenue)" }}
              >
                {excede && <CircleAlert size={12} />}
                {excede && <span>{textoConsultaLarga(limite)}</span>}
                <span style={{ fontFamily: "var(--font-mono)" }}>
                  {largo}/{limite}
                </span>
              </p>
            )}
          </div>
          {/* Atajos de teclado: para lectores de pantalla; a la vista, en el tooltip del campo y de Enviar. */}
          <p id="atajos-consulta" className="sr-only">
            {ATAJOS}
          </p>
        </div>
      </div>

      <style>{`@keyframes rebote { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }`}</style>
    </>
  );
}

/** RR_65 — "Agotaste tus consultas de esta semana. Se restablecen el 26/10/2026, 00:00." */
function avisoSinConsultas(sesion: Sesion): string {
  const periodo = sesion.periodo_consultas === "dia" ? "de hoy" : `de ${PERIODO_ACTUAL[sesion.periodo_consultas]}`;
  return `Agotaste tus consultas ${periodo}. Se restablecen el ${formatearReinicio(sesion.consultas_se_restablecen_en)}.`;
}
