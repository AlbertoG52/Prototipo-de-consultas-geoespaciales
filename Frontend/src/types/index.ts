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

/**
 * Mapa de distribución generado por CR-BioLM. Si `respuesta.mapa` es null no se
 * muestra ningún mapa. La imagen se pide con sesión a `url` (PNG).
 */
export type MapaEspecie = Esquema<"MapaEspecie">;

/**
 * RR_45 — de dónde sale un dato de la respuesta (`respuesta.procedencia`).
 * `dato` dice cuál: especie, texto, elevación, registros o mapa.
 */
export type Procedencia = Esquema<"Procedencia">;

export type DatoRespuesta = Esquema<"DatoRespuesta">;

/** RR_20 — ficha completa de una especie. Lo que no se conoce llega como null. */
export type FichaEspecie = Esquema<"FichaEspecie">;

/**
 * - "resuelta"          → viene `respuesta`
 * - "ambigua"           → viene `candidatos`; hay que preguntarle al usuario (RR_17)
 * - "sin_coincidencias" → no se reconoció ninguna especie
 * - "orientacion"       → no era una consulta (saludo, ayuda, otro idioma…): vienen
 *                         `mensaje`, `motivo` y `ejemplos` (RR_22, RR_32, RR_37, RR_40)
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

// ─── Administración (RR_00_09, RR_76) ───

export type NombreRol = Esquema<"NombreRol">;

/** `actor` es null cuando el cambio se hizo desde el servidor, no desde la aplicación. */
export type RegistroAuditoria = Esquema<"RegistroAuditoria">;

/** RR_76 criterio 3 — cuentas de un rol y cuántas consultas guardadas tienen. */
export type UsoDeRol = Esquema<"UsoDeRol">;

/**
 * RR_76 — consultas de una cuenta. Si `texto_visible` es false, el servidor no
 * manda el texto (ADMIN_VE_TEXTO_CONSULTAS) y cada `texto` llega como null.
 */
export type HistorialUso = Esquema<"HistorialUso">;

export type ConsultaDeUsuario = Esquema<"ConsultaDeUsuario">;

// ─── Preferencias de respuesta (RR_67, RR_68, RR_79, RR_80) ───

/** Si las respuestas incluyen el mapa y las fuentes. */
export type PreferenciasRespuesta = Esquema<"PreferenciasRespuesta">;

/**
 * Las del moderador (RR_67, RR_68): las que aplican, si cada una es propia
 * (`*_propio`) o sigue la del sistema, y la del sistema (`por_defecto`, RR_80).
 */
export type PreferenciasModerador = Esquema<"PreferenciasModerador">;

/** RR_80 — el comportamiento por defecto del sistema y quién lo cambió por última vez. */
export type PreferenciasPorDefecto = Esquema<"PreferenciasPorDefecto">;
