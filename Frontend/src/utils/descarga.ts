/**
 * Descarga de resultados — RR_15.
 *
 * Todo se genera en el navegador a partir de la respuesta ya recibida: no hay
 * petición al backend ni se consume una consulta del límite diario.
 *
 * El mapa no se genera aquí: "Descargar mapa" (components/Mapa.tsx) baja el
 * mismo PNG de CR-BioLM que ya se descargó para mostrarlo.
 */
import { NOMBRE_APP, PREFIJO_ARCHIVOS } from "../config/marca";
import type { FichaEspecie, Procedencia, RespuestaConsulta } from "../types";
import { CELDA_VACIA, ETIQUETAS_DATO, formatearCoordenadas, IDIOMA_FECHAS, SIN_DATO } from "../config/textos";

/** Fecha local en formato AAAA-MM-DD, para los nombres de archivo. */
function fechaCorta(fecha: Date): string {
  const dos = (n: number) => String(n).padStart(2, "0");
  return `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}-${dos(fecha.getDate())}`;
}

/** Nombre base común a los archivos de una misma respuesta. */
export function nombreBase(respuesta: RespuestaConsulta, fecha = new Date()): string {
  return `${PREFIJO_ARCHIVOS}-${respuesta.especie.id}-${fechaCorta(fecha)}`;
}

/**
 * Dispara la descarga de un contenido como archivo.
 *
 * La URL temporal se libera en el siguiente ciclo: revocarla de inmediato
 * cancela la descarga en algunos navegadores (Firefox).
 */
export function descargarArchivo(nombre: string, contenido: string, tipo: string): void {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/**
 * Convierte la respuesta en texto plano legible.
 *
 * Incluye la consulta original para que el archivo quede asociado a la
 * pregunta que lo generó (criterio 3), además del texto, los registros de
 * presencia y las fuentes que se mostraron en pantalla.
 */
export function respuestaATexto(
  consulta: string,
  respuesta: RespuestaConsulta,
  fecha = new Date(),
): string {
  const { especie } = respuesta;
  const lineas: string[] = [
    `${NOMBRE_APP} — Resultado de consulta`,
    `Descargado: ${fecha.toLocaleString(IDIOMA_FECHAS)}`,
    "",
    `Consulta: ${consulta}`,
    "",
    `Especie: ${especie.nombre_cientifico}${especie.nombre_comun ? ` (${especie.nombre_comun})` : ""}`,
    `Familia: ${especie.familia}`,
  ];
  if (respuesta.elevacion) lineas.push(`Elevación: ${respuesta.elevacion}`);

  lineas.push("", respuesta.texto, "");
  // RR_43 y RR_58: el archivo también dice por qué falta el mapa o los registros.
  for (const aviso of respuesta.avisos) lineas.push(`Aviso: ${aviso}`);
  if (respuesta.avisos.length > 0) lineas.push("");

  if (respuesta.registros.length > 0) {
    lineas.push(`Registros de presencia (${respuesta.total_registros}):`);
    for (const r of respuesta.registros) {
      const elevacion = r.elevacion_m !== null ? `${r.elevacion_m} m` : CELDA_VACIA;
      lineas.push(
        `- ${r.localidad} | ${r.fecha} | ${formatearCoordenadas(r)} | ${elevacion} | ${r.fuente}`,
      );
    }
    lineas.push("");
  }

  lineas.push(`Fuentes: ${respuesta.fuentes.join(", ")}`);
  lineas.push(...lineasDeProcedencia(respuesta.procedencia));

  // CRLF para que el Bloc de notas de Windows respete los saltos de línea.
  return lineas.join("\r\n");
}

/** RR_20 — la ficha completa de la especie como texto plano ("Exportar ficha"). */
export function fichaATexto(ficha: FichaEspecie, fecha = new Date()): string {
  const dato = (v: string | null) => v ?? SIN_DATO;
  const lineas: string[] = [
    `${NOMBRE_APP} — Ficha de especie`,
    `Descargado: ${fecha.toLocaleString(IDIOMA_FECHAS)}`,
    "",
    `Nombre científico: ${ficha.nombre_cientifico}`,
    ...(ficha.nombre_comun ? [`Nombre común: ${ficha.nombre_comun}`] : []),
    `Familia: ${ficha.familia}`,
    `Hábitat: ${dato(ficha.habitat)}`,
    // RR_55 criterio 3: sin datos de elevación, el rango se omite.
    ...(ficha.elevacion ? [`Elevación: ${ficha.elevacion}`] : []),
    "",
  ];
  if (ficha.descripcion) lineas.push("Descripción:", ficha.descripcion, "");
  for (const aviso of ficha.avisos) lineas.push(`Aviso: ${aviso}`);
  if (ficha.avisos.length > 0) lineas.push("");
  lineas.push(`Registros de presencia (${ficha.total_registros}):`);
  for (const r of ficha.registros) {
    const elev = r.elevacion_m !== null ? `${r.elevacion_m} msnm` : "sin elevación";
    lineas.push(
      `- ${r.localidad} | ${r.fecha} | ${formatearCoordenadas(r)} | ${elev} | ${r.fuente}`,
    );
  }
  lineas.push("", `Fuentes: ${ficha.fuentes.join(", ")}`);
  lineas.push(...lineasDeProcedencia(ficha.procedencia));
  return lineas.join("\n");
}

/** RR_45: "Origen de los datos" en el archivo descargado. */
function lineasDeProcedencia(procedencia: Procedencia[]): string[] {
  if (procedencia.length === 0) return [];
  return [
    "",
    "Origen de los datos:",
    ...procedencia.map((p) => `- ${ETIQUETAS_DATO[p.dato]}: ${p.fuente} — ${p.detalle}`),
  ];
}
