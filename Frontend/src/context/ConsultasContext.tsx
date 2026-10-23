/**
 * Conversación con el agente e historial de conversaciones.
 *
 * Acá se maneja:
 *
 *  - RR_09  historial por conversaciones, como en un chat: cada conversación
 *           guarda sus consultas en los cuatro estados y se puede reabrir.
 *  - RR_22, RR_32, RR_37, RR_40  un saludo, un pedido de ayuda o un mensaje que
 *           no es una consulta recibe una orientación con ejemplos.
 *  - RR_17  selección de especie cuando la consulta coincide con varias. Con
 *           cuenta, la consulta ambigua queda guardada y pendiente: se puede
 *           elegir la especie incluso al reabrir la conversación otro día.
 *  - RR_36  si nombra varias especies, se pueden buscar todas (buscarTodas).
 *  - RR_00_11 al visitante sin cuenta no se le guarda nada
 *  - RR_05  el error de una consulta se explica en lenguaje sencillo
 *  - RR_38  si la consulta supera el tiempo máximo, se avisa y se puede reintentar
 *
 * Las conversaciones del usuario registrado se cargan del servidor. La del
 * visitante vive solo aquí, en memoria, y desaparece al recargar la página.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import * as api from "../services/api";
import type {
  ConsultaGuardada,
  ConversacionResumen,
  EspecieCandidata,
  RespuestaConsulta,
} from "../types";
import { consultasInsuficientes } from "../utils/especies";
import { useAuth } from "./AuthContext";

/** Un elemento de la conversación. */
export type Mensaje =
  | { clase: "consulta"; id: string; texto: string }
  | { clase: "cargando"; id: string }
  /** `consulta` es el texto que produjo la respuesta; lo usa la descarga (RR_15). */
  | { clase: "respuesta"; id: string; consulta: string; respuesta: RespuestaConsulta }
  | {
      clase: "opciones";
      id: string;
      texto: string;
      candidatos: EspecieCandidata[];
      mensaje: string;
      /** La consulta ambigua guardada; null para un visitante, que no guarda nada. */
      consultaId: number | null;
      /** true cuando ya se eligió una especie: las opciones dejan de poder elegirse. */
      resuelta: boolean;
      /** RR_36: por qué no se buscaron todas (consultas insuficientes). */
      aviso?: string;
    }
  | { clase: "aviso"; id: string; mensaje: string }
  /** RR_22, RR_32, RR_37, RR_40: no era una consulta; se orienta con un mensaje y ejemplos. */
  | { clase: "orientacion"; id: string; mensaje: string; ejemplos: string[] }
  | { clase: "error"; id: string; mensaje: string; textoOriginal: string };

export type Opciones = Extract<Mensaje, { clase: "opciones" }>;

interface EstadoConsultas {
  mensajes: Mensaje[];
  enviando: boolean;

  /** RR_09: conversaciones de la cuenta, la de actividad más reciente primero. */
  conversaciones: ConversacionResumen[];
  /** La conversación abierta; null si es una nueva que todavía no se guardó. */
  conversacionActual: number | null;

  /**
   * Envía una consulta.
   * - `especieId` resuelve una ambigüedad previa (RR_17).
   * - `consultaId` es la consulta ambigua guardada que se resuelve, para que
   *   el servidor no la cobre dos veces.
   */
  enviar: (texto: string, especieId?: string, consultaId?: number | null) => Promise<void>;

  /** RR_36: busca todas las especies de unas opciones, una consulta por especie. */
  buscarTodas: (opciones: Opciones) => Promise<void>;

  /** Reabre una conversación guardada sin reprocesar sus consultas (RR_09). */
  abrirConversacion: (id: number) => Promise<void>;

  /** Empieza una conversación nueva. Las anteriores siguen en el historial. */
  nuevaConsulta: () => void;

  /** Texto de la última consulta, para reintentar tras un error. */
  ultimoTexto: string;
}

const ConsultasContext = createContext<EstadoConsultas | null>(null);

export function useConsultas(): EstadoConsultas {
  const ctx = useContext(ConsultasContext);
  if (!ctx) throw new Error("useConsultas debe usarse dentro de ConsultasProvider");
  return ctx;
}

let contador = 0;
const nuevoId = () => `m${++contador}`;

const MENSAJE_AMBIGUA = "Selecciona la especie que te interesa.";
const MENSAJE_SIN_COINCIDENCIAS = "No se encontró información para esa consulta.";
const MENSAJE_ORIENTACION = "Pregunta por una planta de Costa Rica usando su nombre común o científico.";

const MENSAJE_SIN_CONEXION =
  "No se pudo conectar con el servidor. Revisa tu conexión a internet e intenta de nuevo.";
const MENSAJE_FALLO_SERVIDOR =
  "Ocurrió un problema al procesar tu consulta. Intenta de nuevo en un momento.";

/**
 * RR_38 — segundos que el navegador espera DESPUÉS del tiempo máximo del
 * servidor (Sesion.segundos_maximos_consulta). El servidor corta primero y
 * responde con su propio mensaje; el navegador solo deja de esperar si esa
 * respuesta nunca llega.
 */
const MARGEN_ESPERA_SEGUNDOS = 10;

/**
 * RR_36 — cuántas especies busca "Buscar todas" a la vez; las demás esperan su
 * turno. Una: el LLM de CR-BioLM (RR_49) falla si recibe dos preguntas juntas.
 */
const BUSQUEDAS_SIMULTANEAS = 1;

function mensajeTiempoAgotado(segundos?: number): string {
  const limite = segundos ? ` de ${segundos} ${segundos === 1 ? "segundo" : "segundos"}` : "";
  return `La consulta superó el tiempo máximo${limite}. Puedes reintentarla.`;
}

/**
 * RR_05 criterio 1 — el error de una consulta explicado en lenguaje sencillo.
 *
 * - Sin respuesta del servidor, fetch lanza un TypeError ("Failed to fetch").
 * - RR_38: el servidor cortó la consulta por tiempo (504, con su propio
 *   mensaje) o el navegador dejó de esperar (TiempoAgotado).
 * - Un 5xx o un error sin detalle solo trae "Error 500" y similares.
 * - Los demás (límite de consultas, validaciones) ya vienen del backend
 *   redactados para el usuario y se muestran tal cual.
 */
function mensajeDeError(err: unknown, segundosMaximos?: number): string {
  if (err instanceof api.TiempoAgotado) return mensajeTiempoAgotado(segundosMaximos);
  if (err instanceof TypeError) return MENSAJE_SIN_CONEXION;
  if (!(err instanceof api.ErrorApi)) return MENSAJE_FALLO_SERVIDOR;
  const sinDetalle = /^Error \d+$/.test(err.message);
  if (err.status === 504) return sinDetalle ? mensajeTiempoAgotado(segundosMaximos) : err.message;
  if (err.status >= 500 || sinDetalle) return MENSAJE_FALLO_SERVIDOR;
  return err.message;
}

/** Reconstruye en pantalla una consulta guardada, según su estado. */
function aMensajes(c: ConsultaGuardada): Mensaje[] {
  const pregunta: Mensaje = { clase: "consulta", id: nuevoId(), texto: c.texto };

  if (c.estado === "resuelta" && c.respuesta) {
    return [
      pregunta,
      // Mismo campo `consulta` que una respuesta nueva, para que la descarga
      // (RR_15) funcione igual en una conversación reabierta.
      { clase: "respuesta", id: nuevoId(), consulta: c.texto, respuesta: c.respuesta },
    ];
  }
  if (c.estado === "ambigua") {
    return [
      pregunta,
      {
        clase: "opciones",
        id: nuevoId(),
        texto: c.texto,
        candidatos: c.candidatos,
        mensaje: c.mensaje ?? MENSAJE_AMBIGUA,
        consultaId: c.id,
        resuelta: false,
      },
    ];
  }
  if (c.estado === "orientacion") {
    return [pregunta, orientacion(c.mensaje, c.ejemplos)];
  }
  return [pregunta, { clase: "aviso", id: nuevoId(), mensaje: c.mensaje ?? MENSAJE_SIN_COINCIDENCIAS }];
}

/** El mensaje de una consulta en estado "orientacion", nueva o guardada. */
function orientacion(mensaje: string | null, ejemplos: string[]): Mensaje {
  return { clase: "orientacion", id: nuevoId(), mensaje: mensaje ?? MENSAJE_ORIENTACION, ejemplos };
}

export function ConsultasProvider({ children }: { children: ReactNode }) {
  const { sesion, refrescarSesion } = useAuth();
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [conversaciones, setConversaciones] = useState<ConversacionResumen[]>([]);
  const [conversacionActual, setConversacionActual] = useState<number | null>(null);
  const [enviando, setEnviando] = useState(false);
  const ultimoTexto = useRef("");

  // `enviar` necesita la conversación actual sin volver a crearse cada vez
  // que cambia: por eso también vive en una referencia.
  const conversacionRef = useRef<number | null>(null);
  const cambiarConversacion = useCallback((id: number | null) => {
    conversacionRef.current = id;
    setConversacionActual(id);
  }, []);

  // Al cambiar de cuenta (iniciar o cerrar sesión) se empieza de cero y se
  // cargan las conversaciones de la nueva cuenta. El visitante no tiene.
  const guardaHistorial = sesion?.guarda_historial ?? false;
  const segundosMaximos = sesion?.segundos_maximos_consulta;
  useEffect(() => {
    setMensajes([]);
    cambiarConversacion(null);
    if (!guardaHistorial) {
      setConversaciones([]);
      return;
    }
    let vigente = true;
    api
      .listarConversaciones()
      .then((lista) => {
        if (vigente) setConversaciones(lista);
      })
      .catch(() => {
        if (vigente) setConversaciones([]);
      });
    return () => {
      vigente = false;
    };
  }, [sesion?.tipo, sesion?.usuario?.id, guardaHistorial, cambiarConversacion]);

  /** Sube la conversación al inicio de la lista, o la agrega si es nueva. */
  const tocarConversacion = useCallback((id: number, titulo: string) => {
    const ahora = new Date().toISOString();
    setConversaciones((prev) => {
      const existente = prev.find((c) => c.id === id);
      const actualizada = existente
        ? { ...existente, actualizada_en: ahora }
        : { id, titulo: titulo.slice(0, 120), creada_en: ahora, actualizada_en: ahora };
      return [actualizada, ...prev.filter((c) => c.id !== id)];
    });
  }, []);

  const enviar = useCallback(
    async (texto: string, especieId?: string, consultaId?: number | null) => {
      const limpio = texto.trim();
      if (!limpio || enviando) return;

      ultimoTexto.current = limpio;
      const idCarga = nuevoId();
      const idConsulta = nuevoId();

      // Cuando el usuario elige una especie, la consulta ya está en pantalla (RR_17).
      setMensajes((prev) => [
        ...prev,
        ...(especieId ? [] : [{ clase: "consulta", id: idConsulta, texto: limpio } as Mensaje]),
        { clase: "cargando", id: idCarga },
      ]);
      setEnviando(true);

      try {
        const salida = await api.enviarConsulta(limpio, especieId, {
          conversacionId: conversacionRef.current,
          consultaId,
          esperaMaximaMs:
            segundosMaximos !== undefined
              ? (segundosMaximos + MARGEN_ESPERA_SEGUNDOS) * 1000
              : undefined,
        });

        // RR_09: la consulta quedó guardada en una conversación (solo con cuenta).
        if (salida.conversacion_id !== null) {
          if (conversacionRef.current === null) cambiarConversacion(salida.conversacion_id);
          tocarConversacion(salida.conversacion_id, limpio);
        }

        setMensajes((prev) => {
          // RR_21: la burbuja muestra la consulta como la limpió el servidor (sin
          // emojis ni espacios de más), igual que al reabrir la conversación.
          let sinCarga = prev
            .filter((m) => m.id !== idCarga)
            .map((m) => (m.id === idConsulta && m.clase === "consulta" ? { ...m, texto: salida.texto } : m));
          // Dónde va la respuesta: al final, salvo que resuelva unas opciones.
          let posicion = sinCarga.length;

          // Se eligió una especie: esas opciones ya no se pueden volver a elegir.
          if (especieId && salida.estado === "resuelta") {
            // La última que corresponda (el proyecto usa ES2020, sin findLastIndex).
            let indice = -1;
            sinCarga.forEach((m, i) => {
              if (
                m.clase === "opciones" &&
                !m.resuelta &&
                (consultaId != null ? m.consultaId === consultaId : m.texto === limpio)
              ) {
                indice = i;
              }
            });
            if (indice >= 0) {
              sinCarga = sinCarga.map((m, i) =>
                i === indice && m.clase === "opciones" ? { ...m, resuelta: true } : m,
              );
              // La respuesta va justo debajo de sus opciones, igual que al
              // reabrir la conversación, aunque después haya más consultas.
              posicion = indice + 1;
            }
          }

          if (salida.estado === "ambigua") {
            return [
              ...sinCarga,
              {
                clase: "opciones",
                id: nuevoId(),
                texto: limpio,
                candidatos: salida.candidatos,
                mensaje: salida.mensaje ?? MENSAJE_AMBIGUA,
                consultaId: salida.id,
                resuelta: false,
              },
            ];
          }

          if (salida.estado === "orientacion") {
            return [...sinCarga, orientacion(salida.mensaje, salida.ejemplos)];
          }

          if (salida.estado === "sin_coincidencias") {
            return [
              ...sinCarga,
              {
                clase: "aviso",
                id: nuevoId(),
                mensaje: salida.mensaje ?? MENSAJE_SIN_COINCIDENCIAS,
              },
            ];
          }

          return [
            ...sinCarga.slice(0, posicion),
            // salida.texto es la consulta ya sanitizada por el servidor (RR_00_08).
            { clase: "respuesta", id: nuevoId(), consulta: salida.texto, respuesta: salida.respuesta! },
            ...sinCarga.slice(posicion),
          ];
        });

        // Solo una consulta resuelta consume del límite.
        if (salida.estado === "resuelta") await refrescarSesion();
      } catch (err) {
        const mensaje = mensajeDeError(err, segundosMaximos);
        setMensajes((prev) => [
          ...prev.filter((m) => m.id !== idCarga),
          { clase: "error", id: nuevoId(), mensaje, textoOriginal: limpio },
        ]);
        await refrescarSesion();
      } finally {
        setEnviando(false);
      }
    },
    [enviando, segundosMaximos, refrescarSesion, cambiarConversacion, tocarConversacion],
  );

  /**
   * RR_36 — "Buscar todas": cada especie de las opciones se busca como si se
   * eligiera (RR_17), BUSQUEDAS_SIMULTANEAS a la vez y las demás en cola. Cada
   * una consume una consulta, así que solo se busca si alcanzan para todas; si
   * no, se avisa y las opciones siguen disponibles. Las respuestas quedan debajo
   * de las opciones, en el orden de la lista aunque terminen en otro.
   */
  const buscarTodas = useCallback(
    async (opciones: Opciones) => {
      if (enviando || opciones.resuelta) return;
      const necesarias = opciones.candidatos.length;
      const restantes = sesion?.consultas_restantes ?? 0;
      if (restantes < necesarias) {
        const aviso = consultasInsuficientes(necesarias, restantes);
        setMensajes((prev) =>
          prev.map((m) => (m.id === opciones.id && m.clase === "opciones" ? { ...m, aviso } : m)),
        );
        return;
      }

      // Un lugar por especie debajo de las opciones, en el orden de la lista.
      const lugares = opciones.candidatos.map(() => nuevoId());
      setMensajes((prev) =>
        prev.flatMap((m) =>
          m.id === opciones.id && m.clase === "opciones"
            ? [{ ...m, resuelta: true, aviso: undefined }, ...lugares.map((id): Mensaje => ({ clase: "cargando", id }))]
            : [m],
        ),
      );
      setEnviando(true);
      const poner = (mensaje: Mensaje) => setMensajes((prev) => prev.map((m) => (m.id === mensaje.id ? mensaje : m)));

      const buscar = async (i: number) => {
        const id = lugares[i];
        try {
          const salida = await api.enviarConsulta(opciones.texto, opciones.candidatos[i].id, {
            conversacionId: conversacionRef.current,
            // Con cuenta, la primera resuelve la consulta ambigua guardada y las
            // demás se guardan como consultas nuevas de la misma conversación.
            consultaId: i === 0 ? opciones.consultaId : null,
            esperaMaximaMs:
              segundosMaximos !== undefined
                ? (segundosMaximos + MARGEN_ESPERA_SEGUNDOS) * 1000
                : undefined,
          });
          if (salida.conversacion_id !== null) tocarConversacion(salida.conversacion_id, opciones.texto);
          poner(
            salida.estado === "resuelta" && salida.respuesta
              ? { clase: "respuesta", id, consulta: salida.texto, respuesta: salida.respuesta }
              : { clase: "aviso", id, mensaje: salida.mensaje ?? MENSAJE_SIN_COINCIDENCIAS },
          );
        } catch (err) {
          poner({ clase: "error", id, mensaje: mensajeDeError(err, segundosMaximos), textoOriginal: opciones.texto });
        }
      };

      let siguiente = 0;
      const enTurno = async () => {
        while (siguiente < necesarias) await buscar(siguiente++);
      };
      try {
        await Promise.all(Array.from({ length: Math.min(BUSQUEDAS_SIMULTANEAS, necesarias) }, enTurno));
      } finally {
        setEnviando(false);
        await refrescarSesion();
      }
    },
    [enviando, sesion?.consultas_restantes, segundosMaximos, refrescarSesion, tocarConversacion],
  );

  /**
   * RR_09 — reabrir una conversación guardada. Las respuestas vienen del
   * servidor ya armadas, así que no se reprocesa nada ni se consume ninguna
   * consulta. Las ambiguas que quedaron pendientes vuelven a mostrar sus
   * opciones y se pueden elegir.
   */
  const abrirConversacion = useCallback(
    async (id: number) => {
      cambiarConversacion(id);
      setMensajes([{ clase: "cargando", id: nuevoId() }]);
      try {
        const detalle = await api.obtenerConversacion(id);
        if (conversacionRef.current !== id) return; // se abrió otra mientras cargaba
        setMensajes(detalle.consultas.flatMap(aMensajes));
      } catch {
        if (conversacionRef.current !== id) return;
        setMensajes([
          { clase: "aviso", id: nuevoId(), mensaje: "No se pudo abrir la conversación. Intenta de nuevo." },
        ]);
      }
    },
    [cambiarConversacion],
  );

  const nuevaConsulta = useCallback(() => {
    setMensajes([]);
    cambiarConversacion(null);
  }, [cambiarConversacion]);

  return (
    <ConsultasContext.Provider
      value={{
        mensajes,
        enviando,
        conversaciones,
        conversacionActual,
        enviar,
        buscarTodas,
        abrirConversacion,
        nuevaConsulta,
        ultimoTexto: ultimoTexto.current,
      }}
    >
      {children}
    </ConsultasContext.Provider>
  );
}
