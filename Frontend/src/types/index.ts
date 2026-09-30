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
  /** RR_00_04: minutos sin actividad que cierran la sesión; 0 = nunca; null = visitante. */
  minutos_inactividad: number | null;
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

/** RR_20 — ficha completa de una especie. Lo que no se conoce llega como null. */
export interface FichaEspecie {
  id: string;
  nombre_comun: string | null;
  nombre_cientifico: string;
  familia: string;
  habitat: string | null;
  elevacion: string | null;
  descripcion: string | null;
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
  estado: EstadoConsulta;
  texto: string;
  respuesta: RespuestaConsulta | null;
  candidatos: EspecieCandidata[];
  mensaje: string | null;
  realizada_en: string | null;
  consultas_restantes: number;
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
