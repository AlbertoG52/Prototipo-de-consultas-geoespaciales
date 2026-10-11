/*
 * Tipos compartidos con la API.
 *
 * NO se escriben a mano: salen del contrato OpenAPI del backend, generado a
 * partir de los esquemas de Pydantic (Backend/app/schemas/). Si cambia un
 * esquema, se regeneran con `npm run tipos` (con el backend corriendo) y
 * TypeScript señala cada pantalla que haya que ajustar. Ver README.
 *
 * Este archivo solo les da a los tipos generados (src/types/api.ts) los
 * nombres que usa el frontend.
 */
import type { components } from "./api";

type Esquema<Nombre extends keyof components["schemas"]> = components["schemas"][Nombre];

// ─── Sesión y usuarios ───

/** Una sesión es de un usuario registrado o de un visitante (RR_00_11). */
export type TipoSesion = Esquema<"TipoSesion">;

export type Usuario = Esquema<"UsuarioOut">;

/**
 * Estado de la sesión actual. `guarda_historial` es false para un visitante
 * (RR_00_11); `minutos_inactividad` (RR_00_04) es 0 = nunca y null = visitante.
 */
export type Sesion = Esquema<"SesionOut">;

export type TokenOut = Esquema<"TokenOut">;

export type RegistroRequest = Esquema<"RegistroRequest">;

// ─── Consultas ───

export type EspecieCandidata = Esquema<"EspecieCandidata">;

export type RegistroPresencia = Esquema<"RegistroPresencia">;

export type RespuestaConsulta = Esquema<"RespuestaConsulta">;

/** RR_20 — ficha completa de una especie. Lo que no se conoce llega como null. */
export type FichaEspecie = Esquema<"FichaEspecie">;

/**
 * - "resuelta"          → viene `respuesta`
 * - "ambigua"           → viene `candidatos`; hay que preguntarle al usuario (RR_17)
 * - "sin_coincidencias" → no se reconoció ninguna especie
 */
export type EstadoConsulta = Esquema<"EstadoConsulta">;

/** `conversacion_id` (RR_09) es null para un visitante. */
export type ConsultaOut = Esquema<"ConsultaOut">;

// ─── Historial por conversaciones (RR_09) ───

/** Una consulta guardada dentro de una conversación, en cualquiera de sus estados. */
export type ConsultaGuardada = Esquema<"ConsultaGuardada">;

/** Una entrada de la barra lateral. */
export type ConversacionResumen = Esquema<"ConversacionResumen">;

export type ConversacionDetalle = Esquema<"ConversacionDetalle">;

// ─── Administración (RR_00_09) ───

/** `actor` es null cuando el cambio se hizo desde el servidor, no desde la aplicación. */
export type RegistroAuditoria = Esquema<"RegistroAuditoria">;
