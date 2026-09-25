/**
 * Conversación con el agente e historial de la sesión.
 *
 * Acá se maneja:
 *
 *  - RR_09  historial de la sesión activa
 *  - RR_17  selección de especie cuando la consulta coincide con varias
 *  - RR_00_11 al visitante sin cuenta no se le guarda nada
 *
 * El historial del usuario registrado se carga del servidor, porque sus
 * consultas sí se guardan. El del visitante vive solo aquí, en memoria, y
 * desaparece al recargar la página: eso es para el caso de los usuarios
 * sin cuenta (RR_00_11).
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
import type { EspecieCandidata, ItemHistorial, RespuestaConsulta } from "../types";
import { useAuth } from "./AuthContext";

/** Un elemento de la conversación. */
export type Mensaje =
  | { clase: "consulta"; id: string; texto: string }
  | { clase: "cargando"; id: string }
  | { clase: "respuesta"; id: string; respuesta: RespuestaConsulta }
  | { clase: "opciones"; id: string; texto: string; candidatos: EspecieCandidata[]; mensaje: string }
  | { clase: "aviso"; id: string; mensaje: string }
  | { clase: "error"; id: string; mensaje: string; textoOriginal: string };

interface EstadoConsultas {
  mensajes: Mensaje[];
  historial: ItemHistorial[];
  enviando: boolean;

  /** Envía una consulta. `especieId` resuelve una ambigüedad previa (RR_17). */
  enviar: (texto: string, especieId?: string) => Promise<void>;

  /** Vuelve a mostrar una respuesta guardada sin reprocesarla (RR_09). */
  verDelHistorial: (id: number) => void;

  /** Limpia la conversación. El historial de la sesión no se borra. */
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

export function ConsultasProvider({ children }: { children: ReactNode }) {
  const { sesion, autenticado, refrescarSesion } = useAuth();
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [historial, setHistorial] = useState<ItemHistorial[]>([]);
  const [enviando, setEnviando] = useState(false);
  const ultimoTexto = useRef("");

  // El historial del servidor solo existe para cuentas registradas.
  useEffect(() => {
    if (!sesion) return;
    if (!sesion.guarda_historial) {
      setHistorial([]);
      return;
    }
    api
      .obtenerHistorial()
      .then(setHistorial)
      .catch(() => setHistorial([]));
  }, [sesion?.tipo, sesion?.usuario?.id, autenticado]);

  const enviar = useCallback(
    async (texto: string, especieId?: string) => {
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
        const salida = await api.enviarConsulta(limpio, especieId);

        setMensajes((prev) => {
          const sinCarga = prev.filter((m) => m.id !== idCarga);

          if (salida.estado === "ambigua") {
            return [
              ...sinCarga,
              {
                clase: "opciones",
                id: nuevoId(),
                texto: limpio,
                candidatos: salida.candidatos,
                mensaje: salida.mensaje ?? "Selecciona la especie que te interesa.",
              },
            ];
          }

          if (salida.estado === "sin_coincidencias") {
            return [
              ...sinCarga,
              {
                clase: "aviso",
                id: nuevoId(),
                mensaje: salida.mensaje ?? "No se encontró información para esa consulta.",
              },
            ];
          }

          return [
            ...sinCarga,
            { clase: "respuesta", id: nuevoId(), respuesta: salida.respuesta! },
          ];
        });

        // Solo una consulta resuelta entra al historial y consume del límite.
        if (salida.estado === "resuelta") {
          if (salida.id !== null && salida.respuesta) {
            setHistorial((prev) => [
              ...prev,
              {
                id: salida.id!,
                texto: salida.texto,
                respuesta: salida.respuesta,
                realizada_en: salida.realizada_en ?? new Date().toISOString(),
              },
            ]);
          }
          await refrescarSesion();
        }
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
    [enviando, refrescarSesion],
  );

  /**
   * RR_09 — volver a ver una respuesta anterior sin repetir la
   * consulta. La respuesta viene guardada del servidor, así que esto no hace
   * ninguna petición ni consume una consulta del límite.
   */
  const verDelHistorial = useCallback(
    (id: number) => {
      const entrada = historial.find((h) => h.id === id);
      if (!entrada || !entrada.respuesta) return;
      setMensajes((prev) => [
        ...prev,
        { clase: "consulta", id: nuevoId(), texto: entrada.texto },
        { clase: "respuesta", id: nuevoId(), respuesta: entrada.respuesta! },
      ]);
    },
    [historial],
  );

  const nuevaConsulta = useCallback(() => setMensajes([]), []);

  return (
    <ConsultasContext.Provider
      value={{
        mensajes,
        historial,
        enviando,
        enviar,
        verDelHistorial,
        nuevaConsulta,
        ultimoTexto: ultimoTexto.current,
      }}
    >
      {children}
    </ConsultasContext.Provider>
  );
}
