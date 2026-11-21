/**
 * Estado de la sesión, compartido por toda la aplicación.
 *
 * Si no hay usuario, el backend emite una sesión anónima con menos consultas diarias y sin
 * historial.
 *
 * Expiración por inactividad:
 * - Mientras la persona usa la aplicación (mouse, teclado, scroll, toque) se registra la última
 *   actividad y se renueva el token.
 * - Si pasan `minutos_inactividad` sin actividad, se descarta el token, se vuelve a la sesión
 *   anónima y se marca `sesionExpirada` para pedir un nuevo inicio de sesión.
 * - El servidor aplica lo mismo: el token vence si no se renueva.
 * - La última actividad se guarda en localStorage para que todas las pestañas compartan el mismo
 *   reloj.
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
import type { Sesion } from "../types";

interface EstadoAuth {
  sesion: Sesion | null;
  cargando: boolean;
  error: string | null;

  /** true si hay una cuenta detrás de la sesión. */
  autenticado: boolean;

  /**
   * true mientras el servidor no responde, por ejemplo mientras Docker levanta el backend. La
   * sesión se sigue pidiendo hasta que conteste.
   */
  conectando: boolean;

  entrar: (correo: string, password: string) => Promise<void>;
  /** Devuelve el mensaje del servidor (si se envió el correo de verificación). */
  registrarse: (nombre: string, correo: string, password: string) => Promise<string>;
  salir: () => Promise<void>;

  /** Refresca el contador de consultas tras enviar una. */
  refrescarSesion: () => Promise<void>;
  limpiarError: () => void;

  /** La sesión se cerró por inactividad y hay que volver a entrar. */
  sesionExpirada: boolean;
  limpiarExpiracion: () => void;
}

// Reloj de inactividad compartido entre pestañas.
const CLAVE_ACTIVIDAD = "ultimaActividad";
const EVENTOS_ACTIVIDAD = ["mousemove", "mousedown", "keydown", "scroll", "wheel", "touchstart"] as const;
/** Cada cuánto se revisa si ya se cumplió el periodo de inactividad. */
const MS_REVISION = 5_000;
/** Mínimo entre dos escrituras de la última actividad (mousemove dispara mucho). */
const MS_ENTRE_MARCAS = 2_000;

// Copia en memoria: si localStorage no está disponible el reloj sigue
// funcionando en esta pestaña (y nunca se lee un 0 que cierre la sesión).
let ultimaActividadLocal = Date.now();

function leerUltimaActividad(): number {
  try {
    const guardada = Number(localStorage.getItem(CLAVE_ACTIVIDAD)) || 0;
    return Math.max(guardada, ultimaActividadLocal);
  } catch {
    return ultimaActividadLocal;
  }
}

function guardarUltimaActividad(ms: number) {
  ultimaActividadLocal = ms;
  try {
    localStorage.setItem(CLAVE_ACTIVIDAD, String(ms));
  } catch {
    /* sin almacenamiento el reloj sigue funcionando en esta pestaña */
  }
}

const AuthContext = createContext<EstadoAuth | null>(null);

const esperar = (ms: number) => new Promise((listo) => setTimeout(listo, ms));

/**
 * true si el servidor rechazó el token: venció, se firmó con otra SECRET_KEY o es de una cuenta que
 * no existe en esta base de datos.
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
  const [sesionExpirada, setSesionExpirada] = useState(false);
  const expirando = useRef(false);
  const [conectando, setConectando] = useState(false);

  /**
   * Devuelve la sesión actual. Si el token no sirve o no existe, pide una sesión anónima.
   *
   * Si el servidor no responde, el error se propaga y el token se conserva: un servidor que está
   * arrancando no es motivo para cerrar la sesión.
   */
  const resolverSesion = useCallback(async (): Promise<Sesion> => {
    if (api.obtenerToken()) {
      const eraUsuario = api.tipoDeToken() === "usuario";
      try {
        return await api.obtenerSesion();
      } catch (err) {
        // La cuenta fue desactivada (403); la persona sigue sin cuenta.
        const desactivada = err instanceof api.ErrorApi && err.status === 403;
        // Si solo falló la red (el servidor está arrancando), se conserva el
        // token y el efecto de abajo vuelve a intentar.
        if (!tokenRechazado(err) && !desactivada) throw err;
        // El token de usuario venció mientras la página estaba cerrada.
        if (eraUsuario && !desactivada) setSesionExpirada(true);
        api.borrarToken();
      }
    }
    await api.iniciarSesionAnonima();
    return api.obtenerSesion();
  }, []);

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
      // Con una cuenta, el 401 ya lo atiende expirar(), que avisa que la sesión expiró. Aquí solo
      // se recupera un token anónimo inválido.
      if (sesionRef.current?.tipo === "usuario") return;
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

  /**
   * Cierra la sesión por inactividad. La persona queda como visitante y debe volver a autenticarse.
   * Se protege contra llamadas repetidas (temporizador + 401).
   */
  const expirar = useCallback(async () => {
    if (expirando.current) return;
    expirando.current = true;
    setSesionExpirada(true);
    try {
      api.borrarToken();
      await api.iniciarSesionAnonima();
      setSesion(await api.obtenerSesion());
    } catch {
      setSesion(null);
      setError("No se pudo conectar con el servidor.");
    } finally {
      expirando.current = false;
    }
  }, []);

  // Cualquier 401 con el token de usuario también cierra la sesión. Solo si
  // ya había una sesión de usuario cargada: durante la carga inicial eso lo
  // resuelve resolverSesion.
  const sesionRef = useRef<Sesion | null>(null);
  sesionRef.current = sesion;
  useEffect(() => {
    api.alExpirarSesion(() => {
      if (sesionRef.current?.tipo === "usuario") void expirar();
    });
    return () => api.alExpirarSesion(null);
  }, [expirar]);

  // Temporizador de inactividad: solo para cuentas registradas y cuando el periodo no es "Nunca"
  // (0).
  const minutos = sesion?.tipo === "usuario" ? (sesion.minutos_inactividad ?? 0) : 0;
  useEffect(() => {
    if (minutos <= 0) return;
    const limiteMs = minutos * 60_000;
    // Renovar con más frecuencia que el periodo, pero no en cada evento.
    const msEntreRenovaciones = Math.min(60_000, limiteMs / 4);
    let ultimaMarca = 0;
    // 0: la primera actividad renueva de una vez (tras recargar la página no se
    // sabe cuánto le queda al token).
    let ultimaRenovacion = 0;

    // El reloj arranca al activar el temporizador (carga de la página, inicio
    // de sesión o cambio del periodo en el perfil). Así una marca vieja, p. ej.
    // de cuando el periodo era "Nunca", no cierra la sesión apenas se elige
    // otro. Si el token ya había vencido, el servidor responde 401 y se expira.
    guardarUltimaActividad(Date.now());

    const alActuar = () => {
      const ahora = Date.now();
      if (ahora - ultimaMarca < MS_ENTRE_MARCAS) return;
      ultimaMarca = ahora;
      guardarUltimaActividad(ahora);
      if (ahora - ultimaRenovacion >= msEntreRenovaciones) {
        ultimaRenovacion = ahora;
        // Si el token ya venció, manejar() dispara expirar().
        api.renovarSesion().catch(() => undefined);
      }
    };

    const revisar = () => {
      if (Date.now() - leerUltimaActividad() >= limiteMs) void expirar();
    };

    EVENTOS_ACTIVIDAD.forEach((ev) => window.addEventListener(ev, alActuar, { passive: true }));
    const intervalo = window.setInterval(revisar, MS_REVISION);
    // Al volver a la pestaña se revisa de una vez, sin esperar al intervalo.
    document.addEventListener("visibilitychange", revisar);

    return () => {
      EVENTOS_ACTIVIDAD.forEach((ev) => window.removeEventListener(ev, alActuar));
      window.clearInterval(intervalo);
      document.removeEventListener("visibilitychange", revisar);
    };
  }, [minutos, expirar]);

  const entrar = useCallback(async (correo: string, password: string) => {
    setError(null);
    setCargando(true);
    try {
      await api.iniciarSesion(correo, password);
      // El reloj de inactividad empieza de cero con cada inicio de sesión.
      guardarUltimaActividad(Date.now());
      setSesionExpirada(false);
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
        const { mensaje } = await api.registrar({ nombre, correo, password });
        return mensaje;
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
   * Cierra la sesión activa y vuelve a una sesión anónima, el estado por defecto de la aplicación.
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
  const limpiarExpiracion = useCallback(() => setSesionExpirada(false), []);

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
        sesionExpirada,
        limpiarExpiracion,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
