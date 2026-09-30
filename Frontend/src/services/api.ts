/**
 * Cliente HTTP de la API.
 *
 * Única puerta de salida del frontend hacia el backend: ninguna vista llama a
 * fetch directamente. Así el manejo del token y de los errores vive en un solo
 * lugar.
 */
import type {
  ConsultaOut,
  ConversacionDetalle,
  ConversacionResumen,
  ItemHistorial,
  RegistroAuditoria,
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
 * - `especieId`: la especie que eligió el usuario entre varias coincidencias (RR_17).
 * - `conversacionId`: la conversación donde se guarda; sin ella el servidor
 *   crea una nueva (RR_09). Solo aplica con cuenta.
 * - `consultaId`: la consulta ambigua guardada que se está resolviendo. El
 *   servidor resuelve esa misma consulta, así que no se cobra dos veces.
 */
export async function enviarConsulta(
  texto: string,
  especieId?: string,
  opciones: { conversacionId?: number | null; consultaId?: number | null } = {},
): Promise<ConsultaOut> {
  const res = await fetch(`${API_URL}/consultas`, {
    method: "POST",
    headers: cabeceras(),
    body: JSON.stringify({
      texto,
      especie_id: especieId ?? null,
      conversacion_id: opciones.conversacionId ?? null,
      consulta_id: opciones.consultaId ?? null,
    }),
  });
  return manejar<ConsultaOut>(res);
}

/** RR_09 — conversaciones de la cuenta, la de actividad más reciente primero. */
export async function listarConversaciones(): Promise<ConversacionResumen[]> {
  const res = await fetch(`${API_URL}/conversaciones`, { headers: cabeceras() });
  return manejar<ConversacionResumen[]>(res);
}

/** RR_09 — una conversación completa, para reabrirla sin repetir las consultas. */
export async function obtenerConversacion(id: number): Promise<ConversacionDetalle> {
  const res = await fetch(`${API_URL}/conversaciones/${id}`, { headers: cabeceras() });
  return manejar<ConversacionDetalle>(res);
}

/** Consultas resueltas de la cuenta en una lista plana. La barra lateral usa las conversaciones. */
export async function obtenerHistorial(): Promise<ItemHistorial[]> {
  const res = await fetch(`${API_URL}/consultas/historial`, { headers: cabeceras() });
  return manejar<ItemHistorial[]>(res);
}

// Perfil — solo cuentas registradas; un visitante recibe 401.

/** Cambia el nombre visible de la cuenta. Devuelve el usuario actualizado. */
export async function cambiarNombre(nombre: string): Promise<Usuario> {
  const res = await fetch(`${API_URL}/perfil`, {
    method: "PATCH",
    headers: cabeceras(),
    body: JSON.stringify({ nombre }),
  });
  return manejar<Usuario>(res);
}

/** Cambia la contraseña. El servidor verifica la actual y valida la nueva (RR_00_03). */
export async function cambiarPassword(passwordActual: string, passwordNueva: string): Promise<void> {
  const res = await fetch(`${API_URL}/perfil/password`, {
    method: "POST",
    headers: cabeceras(),
    body: JSON.stringify({ password_actual: passwordActual, password_nueva: passwordNueva }),
  });
  return manejar<void>(res);
}

// Administración — solo supermoderador (RR_00_10); el servidor responde 403 al resto.

export async function listarUsuarios(): Promise<Usuario[]> {
  const res = await fetch(`${API_URL}/admin/usuarios`, { headers: cabeceras() });
  return manejar<Usuario[]>(res);
}

/** RR_00_09 — el cambio queda en la auditoría con quien lo hizo. */
export async function cambiarUsuario(
  id: number,
  campo: "estado" | "rol",
  valor: string,
): Promise<Usuario> {
  const res = await fetch(`${API_URL}/admin/usuarios/${id}/${campo}`, {
    method: "PATCH",
    headers: cabeceras(),
    body: JSON.stringify({ [campo]: valor }),
  });
  return manejar<Usuario>(res);
}

export async function obtenerAuditoria(): Promise<RegistroAuditoria[]> {
  const res = await fetch(`${API_URL}/admin/auditoria`, { headers: cabeceras() });
  return manejar<RegistroAuditoria[]>(res);
}
