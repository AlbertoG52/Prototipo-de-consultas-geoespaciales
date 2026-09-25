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

  entrar: (correo: string, password: string) => Promise<void>;
  registrarse: (nombre: string, correo: string, password: string) => Promise<void>;
  salir: () => Promise<void>;

  /** Refresca el contador de consultas tras enviar una. */
  refrescarSesion: () => Promise<void>;
  limpiarError: () => void;
}

const AuthContext = createContext<EstadoAuth | null>(null);

export function useAuth(): EstadoAuth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Devuelve la sesión actual. Si el token no sirve o no existe, pide una
   * sesión anónima para que la aplicación siga siendo usable (RR_00_11).
   */
  const resolverSesion = useCallback(async (): Promise<Sesion> => {
    if (api.obtenerToken()) {
      try {
        return await api.obtenerSesion();
      } catch {
        api.borrarToken();
      }
    }
    await api.iniciarSesionAnonima();
    return api.obtenerSesion();
  }, []);

  useEffect(() => {
    let vigente = true;
    resolverSesion()
      .then((s) => {
        if (vigente) setSesion(s);
      })
      .catch(() => {
        if (vigente) setError("No se pudo conectar con el servidor.");
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [resolverSesion]);

  const refrescarSesion = useCallback(async () => {
    try {
      setSesion(await api.obtenerSesion());
    } catch {
      /* el contador se actualizará en el siguiente intento */
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
