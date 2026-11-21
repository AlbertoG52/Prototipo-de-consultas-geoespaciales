/*
 * Tipos compartidos con la API.
 *
 * No se escriben a mano: salen del contrato OpenAPI del backend (src/types/api.ts). Si cambia un
 * esquema, se regeneran con `npm run tipos` y TypeScript señala cada pantalla que haya que ajustar.
 * Este archivo solo les da los nombres que usa el frontend.
 */
import type { components } from "./api";

type Esquema<Nombre extends keyof components["schemas"]> = components["schemas"][Nombre];

// ─── Sesión y usuarios ───

/** Una sesión es de un usuario registrado o de un visitante. */
export type TipoSesion = Esquema<"TipoSesion">;

export type Usuario = Esquema<"UsuarioOut">;

/**
 * Estado de la sesión actual. `guarda_historial` es false para un visitante; `minutos_inactividad`
 * es 0 = nunca y null = visitante.
 */
export type Sesion = Esquema<"SesionOut">;

export type TokenOut = Esquema<"TokenOut">;

export type RegistroRequest = Esquema<"RegistroRequest">;

// ─── Consultas ───

export type EspecieCandidata = Esquema<"EspecieCandidata">;

export type RegistroPresencia = Esquema<"RegistroPresencia">;

export type RespuestaConsulta = Esquema<"RespuestaConsulta">;

/**
 * Mapa de distribución generado por CR-BioLM. Si `respuesta.mapa` es null no se muestra ningún
 * mapa. La imagen se pide con sesión a `url` (PNG).
 */
export type MapaEspecie = Esquema<"MapaEspecie">;

/** De dónde sale un dato de la respuesta (`respuesta.procedencia`). */
export type Procedencia = Esquema<"Procedencia">;

export type DatoRespuesta = Esquema<"DatoRespuesta">;

/** Ficha completa de una especie. Lo que no se conoce llega como null. */
export type FichaEspecie = Esquema<"FichaEspecie">;

/**
 * - "resuelta"          → viene `respuesta`
 * - "ambigua"           → viene `candidatos`; el usuario elige la especie
 * - "sin_coincidencias" → no se reconoció ninguna especie
 * - "orientacion"       → no era una consulta (saludo, ayuda, otro idioma…): vienen
 *                         `mensaje`, `motivo` y `ejemplos`
 */
export type EstadoConsulta = Esquema<"EstadoConsulta">;

/** `conversacion_id` es null para un visitante. */
export type ConsultaOut = Esquema<"ConsultaOut">;

// ─── Historial por conversaciones ───

/** Una consulta guardada dentro de una conversación, en cualquiera de sus estados. */
export type ConsultaGuardada = Esquema<"ConsultaGuardada">;

/** Una entrada de la barra lateral. */
export type ConversacionResumen = Esquema<"ConversacionResumen">;

export type ConversacionDetalle = Esquema<"ConversacionDetalle">;

// ─── Administración ───

export type NombreRol = Esquema<"NombreRol">;

/** `actor` es null cuando el cambio se hizo desde el servidor, no desde la aplicación. */
export type RegistroAuditoria = Esquema<"RegistroAuditoria">;

/** Cuentas de un rol y cuántas consultas guardadas tienen. */
export type UsoDeRol = Esquema<"UsoDeRol">;

/** Cada cuánto se restablece el contador de consultas: "dia", "semana" o "mes". */
export type PeriodoConsultas = Esquema<"PeriodoConsultas">;

/** Un rol con su límite de consultas y su periodo. */
export type RolOut = Esquema<"RolOut">;

/**
 * Consultas de una cuenta. Si `texto_visible` es false, el servidor no envía el texto
 * (ADMIN_VE_TEXTO_CONSULTAS) y cada `texto` llega como null.
 */
export type HistorialUso = Esquema<"HistorialUso">;

export type ConsultaDeUsuario = Esquema<"ConsultaDeUsuario">;

// ─── Preferencias de respuesta ───

/** Si las respuestas incluyen el mapa y las fuentes. */
export type PreferenciasRespuesta = Esquema<"PreferenciasRespuesta">;

/**
 * Las del moderador: las que aplican, si cada una es propia (`*_propio`) o sigue la del sistema, y
 * la del sistema (`por_defecto`).
 */
export type PreferenciasModerador = Esquema<"PreferenciasModerador">;

/** Comportamiento por defecto del sistema y quién lo cambió por última vez. */
export type PreferenciasPorDefecto = Esquema<"PreferenciasPorDefecto">;

// ─── Tipos de consulta por rol ───

/** Tipo de pregunta que detecta el backend: distribución, hábitat, descripción o general. */
export type TipoPregunta = Esquema<"TipoPregunta">;

/** Roles que se configuran: visitante, usuario y moderador (el supermoderador puede todo). */
export type RolDeConsulta = Esquema<"RolDeConsulta">;

/** Los tipos permitidos de cada rol y quién los cambió por última vez. */
export type PermisosTiposConsulta = Esquema<"PermisosTiposConsulta">;

export type CambioPermisos = Esquema<"CambioPermisos">;

// ─── Estadísticas de uso ───

/** Periodo de las estadísticas: hoy, últimos 7 o 30 días, o todo. */
export type PeriodoEstadisticas = Esquema<"PeriodoEstadisticas">;

/** Quién hizo las consultas: el rol que la cuenta tiene hoy, o visitante. */
export type GrupoDeUso = Esquema<"GrupoDeUso">;

/** Total, por grupo, por día (últimos 7) y por tipo de pregunta, de un periodo. */
export type EstadisticasUso = Esquema<"EstadisticasUso">;

/** Las cifras de las tarjetas del panel. */
export type ResumenUso = Esquema<"ResumenUso">;
