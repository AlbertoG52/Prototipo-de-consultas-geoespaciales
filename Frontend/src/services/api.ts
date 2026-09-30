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
  EspecieCandidata,
  FichaEspecie,
  ItemHistorial,
  RegistroAuditoria,
  RegistroRequest,
  Sesion,
  TipoSesion,
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

/**
 * Tipo de sesión del token guardado, leído de su contenido sin verificar la
 * firma. Solo sirve para decisiones de interfaz (p. ej. avisar que una sesión
 * de usuario expiró); el servidor es quien valida el token.
 */
export function tipoDeToken(token: string | null = obtenerToken()): TipoSesion | null {
  if (!token) return null;
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const datos = JSON.parse(atob(base64));
    return datos.tipo === "usuario" || datos.tipo === "anonimo" ? datos.tipo : null;
  } catch {
    return null;
  }
}

/**
 * RR_00_04 — aviso de sesión expirada.
 *
 * Cuando una petición hecha con el token de un usuario registrado recibe 401,
 * el token venció (por inactividad) o dejó de ser válido. AuthContext se
 * suscribe aquí para cerrar la sesión y pedir un nuevo inicio de sesión.
 */
let alExpirar: (() => void) | null = null;

export function alExpirarSesion(fn: (() => void) | null) {
  alExpirar = fn;
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
  // RR_00_04: un 401 con el token de un usuario = la sesión venció.
  // (Se excluye el login: ahí un 401 significa credenciales incorrectas.)
  if (res.status === 401 && tipoDeToken() === "usuario" && !res.url.endsWith("/auth/login")) {
    alExpirar?.();
  }

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

/** RR_00_07 — valida el token del enlace de verificación. */
export async function verificarCorreo(token: string): Promise<{ mensaje: string }> {
  const res = await fetch(`${API_URL}/auth/verificar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  return manejar(res);
}

/** RR_00_07 — pide un enlace de verificación nuevo. */
export async function reenviarVerificacion(correo: string): Promise<{ mensaje: string }> {
  const res = await fetch(`${API_URL}/auth/reenviar-verificacion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correo }),
  });
  return manejar(res);
}

/** RR_00_06 — pide el enlace para cambiar la contraseña. */
export async function solicitarRecuperacion(correo: string): Promise<{ mensaje: string }> {
  const res = await fetch(`${API_URL}/auth/recuperar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correo }),
  });
  return manejar(res);
}

/** RR_00_06 — guarda la contraseña nueva con el token del enlace. */
export async function restablecerPassword(token: string, password: string): Promise<{ mensaje: string }> {
  const res = await fetch(`${API_URL}/auth/restablecer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
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

/**
 * RR_00_04 — renueva la sesión porque hubo actividad. El servidor devuelve un
 * token con el periodo de inactividad completo. Si el token ya venció,
 * responde 401 y se dispara el aviso de sesión expirada.
 */
export async function renovarSesion(): Promise<void> {
  const res = await fetch(`${API_URL}/auth/renovar`, { method: "POST", headers: cabeceras() });
  const datos = await manejar<TokenOut>(res);
  guardarToken(datos.access_token);
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

/**
 * RR_00_04 — minutos sin actividad que cierran la sesión (0 = nunca). Guarda
 * el token nuevo que devuelve el servidor para que aplique de inmediato.
 */
export async function cambiarInactividad(minutos: number): Promise<void> {
  const res = await fetch(`${API_URL}/perfil/inactividad`, {
    method: "PATCH",
    headers: cabeceras(),
    body: JSON.stringify({ minutos }),
  });
  const datos = await manejar<TokenOut>(res);
  guardarToken(datos.access_token);
}

/**
 * RR_20 — ficha completa de una especie, por su id del catálogo. No consume
 * consultas del límite diario. Si la especie no existe el servidor responde 404.
 */
export async function obtenerFicha(especieId: string): Promise<FichaEspecie> {
  const res = await fetch(`${API_URL}/especies/${encodeURIComponent(especieId)}`, {
    headers: cabeceras(),
  });
  return manejar<FichaEspecie>(res);
}

/** RR_16 — especies ya consultadas cuyo nombre coincide con `fragmento` (2+ letras). */
export async function sugerirEspecies(fragmento: string): Promise<EspecieCandidata[]> {
  const res = await fetch(`${API_URL}/especies?q=${encodeURIComponent(fragmento)}`, {
    headers: cabeceras(),
  });
  return manejar<EspecieCandidata[]>(res);
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
