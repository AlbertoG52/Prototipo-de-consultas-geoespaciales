/**
 * Cliente HTTP de la API.
 *
 * Única puerta de salida del frontend hacia el backend: ninguna vista llama a
 * fetch directamente. Así el manejo del token y de los errores vive en un solo
 * lugar.
 */
import type {
  ConsultaOut,
  ItemHistorial,
  RegistroRequest,
  Sesion,
  TokenOut,
  Usuario,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const CLAVE_TOKEN = "token";

export function obtenerToken(): string | null {
  return localStorage.getItem(CLAVE_TOKEN);
}

function guardarToken(token: string) {
  localStorage.setItem(CLAVE_TOKEN, token);
}

export function borrarToken() {
  localStorage.removeItem(CLAVE_TOKEN);
}

function cabeceras(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = obtenerToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

/** Error de la API con el código HTTP, para que las vistas puedan distinguir casos. */
export class ErrorApi extends Error {
  status: number;
  constructor(mensaje: string, status: number) {
    super(mensaje);
    this.status = status;
    this.name = "ErrorApi";
  }
}

async function manejar<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const cuerpo = await res.json().catch(() => ({}));
    // FastAPI devuelve 'detail' como texto o como lista de errores de validación.
    let mensaje = `Error ${res.status}`;
    if (typeof cuerpo.detail === "string") {
      mensaje = cuerpo.detail;
    } else if (Array.isArray(cuerpo.detail) && cuerpo.detail.length) {
      mensaje = cuerpo.detail[0].msg?.replace(/^Value error,\s*/, "") ?? mensaje;
    }
    throw new ErrorApi(mensaje, res.status);
  }

  return res.json();
}

// Sesión

/** RR_00_11 — entrar sin cuenta. Se pide en la primera visita. */
export async function iniciarSesionAnonima(): Promise<TokenOut> {
  const res = await fetch(`${API_URL}/auth/anonimo`, { method: "POST" });
  const datos = await manejar<TokenOut>(res);
  guardarToken(datos.access_token);
  return datos;
}

/** RR_00_01 — iniciar sesión con credenciales. */
export async function iniciarSesion(correo: string, password: string): Promise<TokenOut> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correo, password }),
  });
  const datos = await manejar<TokenOut>(res);
  guardarToken(datos.access_token);
  return datos;
}

/** RR_00_01 — crear una cuenta. */
export async function registrar(
  datos: RegistroRequest,
): Promise<{ mensaje: string; usuario: Usuario }> {
  const res = await fetch(`${API_URL}/auth/registro`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  return manejar(res);
}

/** RR_00_01 — cerrar la sesión activa. */
export async function cerrarSesion(): Promise<void> {
  await fetch(`${API_URL}/auth/logout`, { method: "POST", headers: cabeceras() }).catch(
    () => undefined,
  );
  borrarToken();
}

/** Estado de la sesión actual: quién es, cuántas consultas le quedan. */
export async function obtenerSesion(): Promise<Sesion> {
  const res = await fetch(`${API_URL}/auth/sesion`, { headers: cabeceras() });
  return manejar<Sesion>(res);
}

// Consultas 

/**
 * Envía una consulta en lenguaje natural.
 *
 * `especieId` se usa para reenviar la misma consulta cuando el usuario ya
 * eligió entre varias coincidencias (RR_17).
 */
export async function enviarConsulta(texto: string, especieId?: string): Promise<ConsultaOut> {
  const res = await fetch(`${API_URL}/consultas`, {
    method: "POST",
    headers: cabeceras(),
    body: JSON.stringify({ texto, especie_id: especieId ?? null }),
  });
  return manejar<ConsultaOut>(res);
}

/** RR_09 — consultas de la sesión activa, en orden cronológico. */
export async function obtenerHistorial(): Promise<ItemHistorial[]> {
  const res = await fetch(`${API_URL}/consultas/historial`, { headers: cabeceras() });
  return manejar<ItemHistorial[]>(res);
}
