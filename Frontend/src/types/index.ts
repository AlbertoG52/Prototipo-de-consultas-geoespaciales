/* Tipos compartidos con la API */

// ─── Sesión y usuarios ───

/** Una sesión es de un usuario registrado o de un visitante (RR_00_11). */
export type TipoSesion = "usuario" | "anonimo";

export interface Usuario {
  id: number;
  nombre: string | null;
  correo: string;
  rol: "usuario" | "moderador" | "supermoderador";
  estado: "activo" | "inactivo";
  correo_verificado: boolean;
}

export interface Sesion {
  tipo: TipoSesion;
  usuario: Usuario | null;
  limite_consultas: number;
  consultas_realizadas: number;
  consultas_restantes: number;
  /** false para un visitante: sus consultas no se guardan (RR_00_11). */
  guarda_historial: boolean;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  tipo: TipoSesion;
}

export interface RegistroRequest {
  nombre: string;
  correo: string;
  password: string;
}

// Consultas 

export interface EspecieCandidata {
  id: string;
  nombre_comun: string | null;
  nombre_cientifico: string;
  familia: string;
}

export interface RegistroPresencia {
  localidad: string;
  fecha: string;
  latitud: number;
  longitud: number;
  elevacion_m: number | null;
  fuente: string;
}

export interface RespuestaConsulta {
  especie: EspecieCandidata;
  texto: string;
  elevacion: string | null;
  registros: RegistroPresencia[];
  total_registros: number;
  fuentes: string[];
}

/**
 * - "resuelta"          → viene `respuesta`
 * - "ambigua"           → viene `candidatos`; hay que preguntarle al usuario (RR_17)
 * - "sin_coincidencias" → no se reconoció ninguna especie
 */
export type EstadoConsulta = "resuelta" | "ambigua" | "sin_coincidencias";

export interface ConsultaOut {
  id: number | null;
  /** RR_09: conversación donde quedó guardada; null para un visitante. */
  conversacion_id: number | null;
  estado: EstadoConsulta;
  texto: string;
  respuesta: RespuestaConsulta | null;
  candidatos: EspecieCandidata[];
  mensaje: string | null;
  realizada_en: string | null;
  consultas_restantes: number;
}

// Historial por conversaciones (RR_09)

/** Una consulta guardada dentro de una conversación, en cualquiera de sus estados. */
export interface ConsultaGuardada {
  id: number;
  texto: string;
  estado: EstadoConsulta;
  respuesta: RespuestaConsulta | null;
  /** Solo en "ambigua": las opciones, que se pueden elegir al reabrirla. */
  candidatos: EspecieCandidata[];
  mensaje: string | null;
  realizada_en: string;
}

/** Una entrada de la barra lateral. */
export interface ConversacionResumen {
  id: number;
  titulo: string;
  creada_en: string;
  actualizada_en: string;
}

export interface ConversacionDetalle extends ConversacionResumen {
  consultas: ConsultaGuardada[];
}

// Administración (RR_00_09)

export interface RegistroAuditoria {
  id: number;
  accion: string;
  detalle: string | null;
  fecha: string;
  afectado: string | null;
  /** null = el cambio se hizo desde el servidor, no desde la aplicación. */
  actor: string | null;
}

export interface ItemHistorial {
  id: number;
  texto: string;
  respuesta: RespuestaConsulta | null;
  realizada_en: string;
}
