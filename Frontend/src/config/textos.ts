/**
 * Textos y formatos que se repiten en varias pantallas.
 *
 * Se escriben una sola vez aquí para que la tabla de registros, el detalle de
 * un punto del mapa, la ficha y las descargas digan lo mismo.
 */
import type {
  DatoRespuesta,
  EstadoConsulta,
  NombreRol,
  RegistroPresencia,
  RolDeConsulta,
  TipoPregunta,
} from "../types";

/** Idioma y región para mostrar fechas y horas (toLocaleString, toLocaleDateString). */
export const IDIOMA_FECHAS = "es-CR";

/** Valor que se muestra cuando un campo no tiene dato. */
export const SIN_DATO = "Sin dato";

/** Marca corta para una celda vacía de una tabla. */
export const CELDA_VACIA = "—";

/** Nombres de los campos de un registro de presencia. */
export const ETIQUETAS_REGISTRO = {
  localidad: "Localidad",
  fecha: "Fecha",
  fechaDelRegistro: "Fecha del registro",
  coordenadas: "Coordenadas",
  elevacion: "Elevación",
  fuente: "Fuente",
} as const;

/** Encabezados de la tabla de registros (respuesta del agente y ficha de especie). */
export const COLUMNAS_TABLA_REGISTROS = [
  ETIQUETAS_REGISTRO.localidad,
  ETIQUETAS_REGISTRO.fecha,
  ETIQUETAS_REGISTRO.coordenadas,
  ETIQUETAS_REGISTRO.elevacion,
] as const;

/**
 * RR_59 — cantidad de registros de presencia, en singular o plural:
 * "Sin registros", "1 registro", "150 registros".
 */
export function textoRegistros(cantidad: number): string {
  if (cantidad === 0) return "Sin registros";
  return `${cantidad.toLocaleString(IDIOMA_FECHAS)} ${cantidad === 1 ? "registro" : "registros"}`;
}

/**
 * RR_34 — largo de una consulta como lo cuenta el servidor: por caracteres, no
 * por unidades UTF-16 (un emoji cuenta 1, no 2).
 */
export const largoConsulta = (texto: string) => [...texto].length;

/** RR_34 criterio 2 — aviso cuando la consulta pasa el límite. */
export const textoConsultaLarga = (limite: number) =>
  `La consulta supera el límite de ${limite.toLocaleString(IDIOMA_FECHAS)} caracteres. Acórtala para enviarla.`;

/** Latitud y longitud con cuatro decimales (unos 11 m de precisión). */
export function formatearCoordenadas(registro: Pick<RegistroPresencia, "latitud" | "longitud">): string {
  return `${registro.latitud.toFixed(4)}, ${registro.longitud.toFixed(4)}`;
}

/**
 * RR_51 — nombres de las fuentes tal como los manda el backend en
 * `procedencia.fuente` (constantes MANUAL y GBIF de
 * Backend/app/services/contexto_especie.py). Si cambian allá, cambiarlos aquí.
 */
export const FUENTE_MANUAL = "Manual de Plantas de Costa Rica";
export const FUENTE_GBIF = "GBIF";

/** RR_45 — nombre de cada dato en "Origen de los datos" (campo `procedencia`). */
export const ETIQUETAS_DATO: Record<DatoRespuesta, string> = {
  especie: "Especie",
  texto: "Texto",
  elevacion: "Elevación",
  registros: "Registros de presencia",
  mapa: "Mapa",
};

/** Un número con separador de miles: 2841 → "2 841". */
export const formatearNumero = (numero: number) => numero.toLocaleString(IDIOMA_FECHAS);

/** Nombre visible de cada rol (panel de administración). */
export const ETIQUETAS_ROL: Record<NombreRol, string> = {
  usuario: "Usuario",
  moderador: "Moderador",
  supermoderador: "Supermoderador",
};

/** RR_77 — los roles a los que se les configuran los tipos de consulta, más el visitante. */
export const ETIQUETAS_ROL_DE_CONSULTA: Record<RolDeConsulta, string> = {
  visitante: "Visitante",
  usuario: ETIQUETAS_ROL.usuario,
  moderador: ETIQUETAS_ROL.moderador,
};

/** RR_77 — nombre de cada tipo de pregunta que detecta el backend (TipoPregunta). */
export const ETIQUETAS_TIPO_PREGUNTA: Record<TipoPregunta, string> = {
  distribucion: "Distribución",
  habitat: "Hábitat",
  descripcion: "Descripción",
  general: "Información general",
};

/** Cómo terminó una consulta guardada (columna consultas.estado). */
export const ETIQUETAS_ESTADO_CONSULTA: Record<EstadoConsulta, string> = {
  resuelta: "Resuelta",
  ambigua: "Pendiente de elegir especie",
  sin_coincidencias: "Sin coincidencias",
  orientacion: "Orientación (saludo, ayuda…)",
};
