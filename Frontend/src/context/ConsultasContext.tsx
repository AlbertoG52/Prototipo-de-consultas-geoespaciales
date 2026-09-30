/**
 * Conversación con el agente e historial de conversaciones.
 *
 * Acá se maneja:
 *
 *  - RR_09  historial por conversaciones, como en un chat: cada conversación
 *           guarda sus consultas en los tres estados y se puede reabrir.
 *  - RR_17  selección de especie cuando la consulta coincide con varias. Con
 *           cuenta, la consulta ambigua queda guardada y pendiente: se puede
 *           elegir la especie incluso al reabrir la conversación otro día.
 *  - RR_00_11 al visitante sin cuenta no se le guarda nada
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
    }
  | { clase: "aviso"; id: string; mensaje: string }
  | { clase: "error"; id: string; mensaje: string; textoOriginal: string };

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
  return [pregunta, { clase: "aviso", id: nuevoId(), mensaje: c.mensaje ?? MENSAJE_SIN_COINCIDENCIAS }];
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

      // Cuando el usuario elige una especie, la consulta ya está en pantalla (RR_17).
      setMensajes((prev) => [
        ...prev,
        ...(especieId ? [] : [{ clase: "consulta", id: nuevoId(), texto: limpio } as Mensaje]),
        { clase: "cargando", id: idCarga },
      ]);
      setEnviando(true);

      try {
        const salida = await api.enviarConsulta(limpio, especieId, {
          conversacionId: conversacionRef.current,
          consultaId,
        });

        // RR_09: la consulta quedó guardada en una conversación (solo con cuenta).
        if (salida.conversacion_id !== null) {
          if (conversacionRef.current === null) cambiarConversacion(salida.conversacion_id);
          tocarConversacion(salida.conversacion_id, limpio);
        }

        setMensajes((prev) => {
          let sinCarga = prev.filter((m) => m.id !== idCarga);
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
        const mensaje =
          err instanceof Error ? err.message : "No se pudo procesar la consulta.";
        setMensajes((prev) => [
          ...prev.filter((m) => m.id !== idCarga),
          { clase: "error", id: nuevoId(), mensaje, textoOriginal: limpio },
        ]);
        await refrescarSesion();
      } finally {
        setEnviando(false);
      }
    },
    [enviando, refrescarSesion, cambiarConversacion, tocarConversacion],
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
        abrirConversacion,
        nuevaConsulta,
        ultimoTexto: ultimoTexto.current,
      }}
    >
      {children}
    </ConsultasContext.Provider>
  );
}
