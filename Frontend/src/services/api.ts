/**
 * Cliente HTTP de la API.
 *
 * Única puerta de salida del frontend hacia el backend: ninguna vista llama a
 * fetch directamente. Así el manejo del token y de los errores vive en un solo
 * lugar.
 */
import type {
  CambioPermisos,
  ConsultaOut,
  ConversacionDetalle,
  ConversacionResumen,
  EspecieCandidata,
  EstadisticasUso,
  FichaEspecie,
  HistorialUso,
  PeriodoEstadisticas,
  PermisosTiposConsulta,
  PreferenciasModerador,
  PreferenciasPorDefecto,
  PreferenciasRespuesta,
  RegistroAuditoria,
  RegistroRequest,
  ResumenUso,
  Sesion,
  TipoSesion,
  TokenOut,
  Usuario,
  UsoDeRol,
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

/**
 * RR_38 — el navegador dejó de esperar la respuesta.
 *
 * El servidor corta la consulta al llegar a su tiempo máximo y responde 504;
 * este error es la red de seguridad para cuando ni siquiera esa respuesta llega
 * (servidor colgado o red caída a mitad de la petición).
 */
export class TiempoAgotado extends Error {
  constructor() {
    super("Se agotó el tiempo de espera de la respuesta.");
    this.name = "TiempoAgotado";
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

/**
 * Hace una petición a la API con el token guardado y devuelve el cuerpo ya
 * interpretado (o lanza ErrorApi). Los endpoints públicos ignoran el token.
 *
 * Con `esperaMaximaMs`, la petición se cancela si no termina en ese tiempo y
 * se lanza TiempoAgotado (RR_38).
 */
async function pedir<T>(
  ruta: string,
  metodo = "GET",
  cuerpo?: unknown,
  esperaMaximaMs?: number,
): Promise<T> {
  const control = esperaMaximaMs ? new AbortController() : undefined;
  const reloj = control ? setTimeout(() => control.abort(), esperaMaximaMs) : undefined;
  try {
    const res = await fetch(`${API_URL}${ruta}`, {
      method: metodo,
      headers: cabeceras(),
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      signal: control?.signal,
    });
    return await manejar<T>(res);
  } catch (err) {
    if (control?.signal.aborted) throw new TiempoAgotado();
    throw err;
  } finally {
    clearTimeout(reloj);
  }
}

/** Pide un token nuevo al servidor y lo guarda. */
async function pedirToken(ruta: string, metodo = "POST", cuerpo?: unknown): Promise<TokenOut> {
  const datos = await pedir<TokenOut>(ruta, metodo, cuerpo);
  guardarToken(datos.access_token);
  return datos;
}

type Mensaje = { mensaje: string };

// Sesión

/** RR_00_11 — entrar sin cuenta. Se pide en la primera visita. */
export const iniciarSesionAnonima = () => pedirToken("/auth/anonimo");

/** RR_00_01 — iniciar sesión con credenciales. */
export const iniciarSesion = (correo: string, password: string) =>
  pedirToken("/auth/login", "POST", { correo, password });

/** RR_00_01 — crear una cuenta. */
export const registrar = (datos: RegistroRequest) =>
  pedir<Mensaje & { usuario: Usuario }>("/auth/registro", "POST", datos);

/** RR_00_07 — valida el token del enlace de verificación. */
export const verificarCorreo = (token: string) => pedir<Mensaje>("/auth/verificar", "POST", { token });

/** RR_00_07 — pide un enlace de verificación nuevo. */
export const reenviarVerificacion = (correo: string) =>
  pedir<Mensaje>("/auth/reenviar-verificacion", "POST", { correo });

/** RR_00_06 — pide el enlace para cambiar la contraseña. */
export const solicitarRecuperacion = (correo: string) =>
  pedir<Mensaje>("/auth/recuperar", "POST", { correo });

/** RR_00_06 — guarda la contraseña nueva con el token del enlace. */
export const restablecerPassword = (token: string, password: string) =>
  pedir<Mensaje>("/auth/restablecer", "POST", { token, password });

/** RR_00_01 — cerrar la sesión activa. El token se descarta aunque el servidor no responda. */
export async function cerrarSesion(): Promise<void> {
  await pedir<void>("/auth/logout", "POST").catch(() => undefined);
  borrarToken();
}

/** Estado de la sesión actual: quién es, cuántas consultas le quedan. */
export const obtenerSesion = () => pedir<Sesion>("/auth/sesion");

/**
 * RR_00_04 — renueva la sesión porque hubo actividad. El servidor devuelve un
 * token con el periodo de inactividad completo. Si el token ya venció,
 * responde 401 y se dispara el aviso de sesión expirada.
 */
export async function renovarSesion(): Promise<void> {
  await pedirToken("/auth/renovar");
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
 * - `esperaMaximaMs`: cuánto esperar la respuesta antes de lanzar TiempoAgotado (RR_38).
 */
export const enviarConsulta = (
  texto: string,
  especieId?: string,
  opciones: {
    conversacionId?: number | null;
    consultaId?: number | null;
    esperaMaximaMs?: number;
  } = {},
) =>
  pedir<ConsultaOut>(
    "/consultas",
    "POST",
    {
      texto,
      especie_id: especieId ?? null,
      conversacion_id: opciones.conversacionId ?? null,
      consulta_id: opciones.consultaId ?? null,
    },
    opciones.esperaMaximaMs,
  );

/** RR_09 — conversaciones de la cuenta, la de actividad más reciente primero. */
export const listarConversaciones = () => pedir<ConversacionResumen[]>("/conversaciones");

/** RR_09 — una conversación completa, para reabrirla sin repetir las consultas. */
export const obtenerConversacion = (id: number) => pedir<ConversacionDetalle>(`/conversaciones/${id}`);

// Perfil — solo cuentas registradas; un visitante recibe 401.

/** Cambia el nombre visible de la cuenta. Devuelve el usuario actualizado. */
export const cambiarNombre = (nombre: string) => pedir<Usuario>("/perfil", "PATCH", { nombre });

/** Cambia la contraseña. El servidor verifica la actual y valida la nueva (RR_00_03). */
export const cambiarPassword = (passwordActual: string, passwordNueva: string) =>
  pedir<void>("/perfil/password", "POST", {
    password_actual: passwordActual,
    password_nueva: passwordNueva,
  });

/**
 * RR_00_04 — minutos sin actividad que cierran la sesión (0 = nunca). Guarda
 * el token nuevo que devuelve el servidor para que aplique de inmediato.
 */
export async function cambiarInactividad(minutos: number): Promise<void> {
  await pedirToken("/perfil/inactividad", "PATCH", { minutos });
}

/** RR_67, RR_68, RR_79 — preferencias de respuesta del moderador (otro rol: 403). */
export const obtenerPreferencias = () => pedir<PreferenciasModerador>("/perfil/preferencias");

/**
 * RR_67, RR_68 — cambia si las respuestas del moderador incluyen el mapa o las
 * fuentes. Solo se envían los campos que cambian; `null` vuelve a la del
 * sistema (RR_80). Aplica desde la consulta siguiente.
 */
export const cambiarPreferencias = (cambio: {
  incluir_mapa?: boolean | null;
  incluir_fuentes?: boolean | null;
}) => pedir<PreferenciasModerador>("/perfil/preferencias", "PATCH", cambio);

// Especies — no consumen consultas del límite diario.

/** RR_20 — ficha completa de una especie, por su id del catálogo. 404 si no existe. */
export const obtenerFicha = (especieId: string) =>
  pedir<FichaEspecie>(`/especies/${encodeURIComponent(especieId)}`);

/**
 * Ruta válida del mapa de una especie, tal como la arma el backend en
 * `MapaEspecie.url`. Se exige este formato antes de pedirla para que el token
 * nunca se envíe a otra dirección.
 */
const RUTA_MAPA = /^\/especies\/[a-z0-9-]+\/mapa$/;

/**
 * RR_46 — imagen PNG del mapa de distribución generado por CR-BioLM.
 *
 * El endpoint pide sesión, así que un <img src> directo no sirve (no envía el
 * token): se descarga aquí con el header Authorization y se devuelve como
 * Blob. Quien la muestre crea la URL con URL.createObjectURL y la libera con
 * URL.revokeObjectURL al desmontarse. `ruta` es `MapaEspecie.url`.
 */
export async function obtenerImagenMapa(ruta: string): Promise<Blob> {
  if (!RUTA_MAPA.test(ruta)) throw new ErrorApi("La dirección del mapa no es válida.", 400);
  const res = await fetch(`${API_URL}${ruta}`, { headers: cabeceras() });
  // Un error se interpreta igual que en las demás peticiones (incluido el 401).
  if (!res.ok) return manejar<never>(res);
  return res.blob();
}

/** RR_16 — especies ya consultadas cuyo nombre coincide con `fragmento` (2+ letras). */
export const sugerirEspecies = (fragmento: string) =>
  pedir<EspecieCandidata[]>(`/especies?q=${encodeURIComponent(fragmento)}`);

// Administración — solo supermoderador (RR_00_10); el servidor responde 403 al resto.

export const listarUsuarios = () => pedir<Usuario[]>("/admin/usuarios");

/** RR_00_09 — el cambio queda en la auditoría con quien lo hizo. */
export const cambiarUsuario = (id: number, campo: "estado" | "rol", valor: string) =>
  pedir<Usuario>(`/admin/usuarios/${id}/${campo}`, "PATCH", { [campo]: valor });

export const obtenerAuditoria = () => pedir<RegistroAuditoria[]>("/admin/auditoria");

/** RR_80 — comportamiento por defecto de las respuestas (mapa y fuentes). */
export const obtenerPreferenciasPorDefecto = () =>
  pedir<PreferenciasPorDefecto>("/admin/preferencias-respuesta");

/** RR_80 criterio 3 — aplica a todos los que no han cambiado su preferencia. */
export const cambiarPreferenciasPorDefecto = (preferencias: PreferenciasRespuesta) =>
  pedir<PreferenciasPorDefecto>("/admin/preferencias-respuesta", "PUT", preferencias);

/** RR_77 — los tipos de consulta que puede hacer cada rol. */
export const obtenerPermisosDeConsulta = () => pedir<PermisosTiposConsulta>("/admin/permisos-consulta");

/** RR_77 criterio 1 — deja permitidos solo los tipos enviados de cada rol. */
export const cambiarPermisosDeConsulta = (cambio: CambioPermisos) =>
  pedir<PermisosTiposConsulta>("/admin/permisos-consulta", "PUT", cambio);

/** RR_78 — total de consultas del periodo, por rol, por día y por tipo de pregunta. */
export const obtenerEstadisticas = (periodo: PeriodoEstadisticas) =>
  pedir<EstadisticasUso>(`/admin/estadisticas?periodo=${periodo}`);

/** RR_78 — cifras de las tarjetas del panel (cuentas, consultas de hoy, ayer y 30 días). */
export const obtenerResumenDeUso = () => pedir<ResumenUso>("/admin/estadisticas/resumen");

/** RR_76 — una página del historial de uso de una cuenta, de lo más reciente a lo más antiguo. */
export const obtenerHistorialDeUso = (usuarioId: number, limite: number, desplazamiento: number) =>
  pedir<HistorialUso>(
    `/admin/usuarios/${usuarioId}/consultas?limite=${limite}&desplazamiento=${desplazamiento}`,
  );

/** RR_76 criterio 3 — cuentas y consultas guardadas de cada rol. */
export const obtenerUsoPorRol = () => pedir<UsoDeRol[]>("/admin/uso-por-rol");
