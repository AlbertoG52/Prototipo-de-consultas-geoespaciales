/**
 * Textos y formatos que se repiten en varias pantallas.
 *
 * Se escriben una sola vez aquí para que la tabla de registros, el detalle de
 * un punto del mapa, la ficha y las descargas digan lo mismo.
 */
import type {
  DatoRespuesta,
  EstadoConsulta,
  GrupoDeUso,
  NombreRol,
  PeriodoConsultas,
  PeriodoEstadisticas,
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

/** Cantidad de registros de presencia: "Sin registros", "1 registro", "150 registros". */
export function textoRegistros(cantidad: number): string {
  if (cantidad === 0) return "Sin registros";
  return `${cantidad.toLocaleString(IDIOMA_FECHAS)} ${cantidad === 1 ? "registro" : "registros"}`;
}

/**
 * De cuándo son los registros de GBIF: "GBIF al 18/10/2026". La fecha llega en
 * `registros_actualizados_en` (ISO, UTC) y se muestra en la hora del navegador.
 */
export function textoActualizacionGbif(iso: string): string {
  return `GBIF al ${new Date(iso).toLocaleDateString(IDIOMA_FECHAS)}`;
}

/** Explicación de la etiqueta anterior, para el `title`. */
export const AYUDA_ACTUALIZACION_GBIF =
  "Fecha en que se descargaron de GBIF los registros de presencia. Se actualizan periódicamente.";

/**
 * Largo de una consulta como lo cuenta el servidor: por caracteres, no por unidades UTF-16 (un
 * emoji cuenta 1, no 2).
 */
export const largoConsulta = (texto: string) => [...texto].length;

/** Aviso cuando la consulta pasa el límite. */
export const textoConsultaLarga = (limite: number) =>
  `La consulta supera el límite de ${limite.toLocaleString(IDIOMA_FECHAS)} caracteres. Acórtala para enviarla.`;

/** Latitud y longitud con cuatro decimales (unos 11 m de precisión). */
export function formatearCoordenadas(registro: Pick<RegistroPresencia, "latitud" | "longitud">): string {
  return `${registro.latitud.toFixed(4)}, ${registro.longitud.toFixed(4)}`;
}

/**
 * Nombres de las fuentes como los envía el backend en `procedencia.fuente` (MANUAL y GBIF de
 * Backend/app/services/contexto_especie.py). Si cambian allá, se cambian aquí.
 */
export const FUENTE_MANUAL = "Manual de Plantas de Costa Rica";
export const FUENTE_GBIF = "GBIF";

/** Nombre de cada dato en "Origen de los datos" (campo `procedencia`). */
export const ETIQUETAS_DATO: Record<DatoRespuesta, string> = {
  especie: "Especie",
  texto: "Texto",
  elevacion: "Elevación",
  registros: "Registros de presencia",
  mapa: "Mapa",
};

/** Un número con separador de miles: 2841 → "2 841". */
export const formatearNumero = (numero: number) => numero.toLocaleString(IDIOMA_FECHAS);

/** Cada cuánto se restablece el contador, junto a un límite: "20 por día". */
export const ETIQUETAS_PERIODO_CONSULTAS: Record<PeriodoConsultas, string> = {
  dia: "por día",
  semana: "por semana",
  mes: "por mes",
};

/** El periodo actual, en el contador: "5/20 consultas esta semana". */
export const PERIODO_ACTUAL: Record<PeriodoConsultas, string> = {
  dia: "hoy",
  semana: "esta semana",
  mes: "este mes",
};

/** Cuándo se restablece el contador, en la hora del navegador: "20/10/2026, 00:00". */
export const formatearReinicio = (iso: string) =>
  new Date(iso).toLocaleString(IDIOMA_FECHAS, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23", // "00:00", no "12:00 a. m."
  });

/** Nombre visible de cada rol (panel de administración). */
export const ETIQUETAS_ROL: Record<NombreRol, string> = {
  usuario: "Usuario",
  moderador: "Moderador",
  supermoderador: "Supermoderador",
};

/** Roles a los que se les configuran los tipos de consulta, más el visitante. */
export const ETIQUETAS_ROL_DE_CONSULTA: Record<RolDeConsulta, string> = {
  visitante: "Visitante",
  usuario: ETIQUETAS_ROL.usuario,
  moderador: ETIQUETAS_ROL.moderador,
};

/** Quién hizo las consultas: el rol actual de la cuenta, o visitante. */
export const ETIQUETAS_GRUPO_DE_USO: Record<GrupoDeUso, string> = {
  visitante: ETIQUETAS_ROL_DE_CONSULTA.visitante,
  ...ETIQUETAS_ROL,
};

/** Periodos de las estadísticas de uso. */
export const ETIQUETAS_PERIODO: Record<PeriodoEstadisticas, string> = {
  hoy: "Hoy",
  ultimos_7_dias: "Últimos 7 días",
  ultimos_30_dias: "Últimos 30 días",
  todo: "Todo",
};

/** Una fracción entre 0 y 1 como porcentaje: 0.964 → "96,4 %". */
export const formatearPorcentaje = (fraccion: number) =>
  fraccion.toLocaleString(IDIOMA_FECHAS, { style: "percent", maximumFractionDigits: 1 });

/** Nombre de cada tipo de pregunta que detecta el backend (TipoPregunta). */
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
