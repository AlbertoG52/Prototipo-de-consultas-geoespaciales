/**
 * Estado de la sesión, compartido por toda la aplicación.
 *
 * Si no hay usuario, el backend emite una sesión anónima con menos
 * consultas diarias y sin historial (RR_00_11). 
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import * as api from "../services/api";
import type { Sesion } from "../types";

interface EstadoAuth {
  sesion: Sesion | null;
  cargando: boolean;
  error: string | null;

  /** true si hay una cuenta detrás de la sesión. */
  autenticado: boolean;

  /**
   * true mientras el servidor no responde, por ejemplo mientras Docker todavía
   * levanta el backend. La sesión se sigue pidiendo sola hasta que conteste.
   */
  conectando: boolean;

  entrar: (correo: string, password: string) => Promise<void>;
  registrarse: (nombre: string, correo: string, password: string) => Promise<void>;
  salir: () => Promise<void>;

  /** Refresca el contador de consultas tras enviar una. */
  refrescarSesion: () => Promise<void>;
  limpiarError: () => void;
}

const AuthContext = createContext<EstadoAuth | null>(null);

const esperar = (ms: number) => new Promise((listo) => setTimeout(listo, ms));

/**
 * true si el servidor rechazó el token: venció, se firmó con otra SECRET_KEY o
 * es de una cuenta que no existe en esta base de datos (por ejemplo, después
 * de reiniciarla o de pasar de la base local a la de AWS).
 */
function tokenRechazado(err: unknown): boolean {
  return err instanceof api.ErrorApi && err.status === 401;
}

export function useAuth(): EstadoAuth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conectando, setConectando] = useState(false);

  /**
   * Devuelve la sesión actual. Si el token no sirve o no existe, pide una
   * sesión anónima para que la aplicación siga siendo usable (RR_00_11).
   *
   * Si el servidor no responde, el error se propaga y el token se conserva:
   * un servidor que está arrancando no es motivo para cerrar la sesión.
   */
  const resolverSesion = useCallback(async (): Promise<Sesion> => {
    if (api.obtenerToken()) {
      try {
        return await api.obtenerSesion();
      } catch (err) {
        if (!tokenRechazado(err)) throw err;
        api.borrarToken();
      }
    }
    await api.iniciarSesionAnonima();
    return api.obtenerSesion();
  }, []);

  // Con "docker compose up" el frontend queda listo antes que el backend, que
  // espera a la base de datos y aplica las migraciones. Por eso, si el primer
  // intento falla, se reintenta solo en vez de dejar la aplicación sin sesión.
  useEffect(() => {
    let vigente = true;
    (async () => {
      for (let intento = 1; vigente; intento++) {
        try {
          const s = await resolverSesion();
          if (!vigente) return;
          setSesion(s);
          setConectando(false);
          setCargando(false);
          return;
        } catch {
          if (!vigente) return;
          setConectando(true);
          await esperar(Math.min(1000 * intento, 5000));
        }
      }
    })();
    return () => {
      vigente = false;
    };
  }, [resolverSesion]);

  const refrescarSesion = useCallback(async () => {
    try {
      setSesion(await api.obtenerSesion());
    } catch (err) {
      // Si solo falló la red, el contador se actualizará en el siguiente intento.
      if (!tokenRechazado(err)) return;
      // El token dejó de servir con la aplicación abierta (venció o se
      // reinició la base de datos): se continúa como visitante en vez de
      // dejar la aplicación sin poder consultar.
      try {
        api.borrarToken();
        await api.iniciarSesionAnonima();
        setSesion(await api.obtenerSesion());
      } catch {
        /* sin servidor: se reintentará en la siguiente acción */
      }
    }
  }, []);

  const entrar = useCallback(async (correo: string, password: string) => {
    setError(null);
    setCargando(true);
    try {
      await api.iniciarSesion(correo, password);
      setSesion(await api.obtenerSesion());
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
      throw err;
    } finally {
      setCargando(false);
    }
  }, []);

  const registrarse = useCallback(
    async (nombre: string, correo: string, password: string) => {
      setError(null);
      setCargando(true);
      try {
        await api.registrar({ nombre, correo, password });
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo crear la cuenta.");
        throw err;
      } finally {
        setCargando(false);
      }
    },
    [],
  );

  /**
   * RR_00_01 — cerrar la sesión activa.
   *
   * No deja al usuario sin sesión: lo devuelve a una anónima, que es el estado
   * por defecto de la aplicación.
   */
  const salir = useCallback(async () => {
    setCargando(true);
    try {
      await api.cerrarSesion();
      await api.iniciarSesionAnonima();
      setSesion(await api.obtenerSesion());
    } catch {
      setError("No se pudo cerrar la sesión.");
    } finally {
      setCargando(false);
    }
  }, []);

  const limpiarError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider
      value={{
        sesion,
        cargando,
        error,
        autenticado: sesion?.tipo === "usuario",
        conectando,
        entrar,
        registrarse,
        salir,
        refrescarSesion,
        limpiarError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
