/**
 * Descarga de resultados — RR_15.
 *
 * Todo se genera en el navegador a partir de la respuesta ya recibida: no hay
 * petición al backend ni se consume una consulta del límite diario.
 *
 * El mapa que se descarga es el SVG provisional de ChatPage. Cuando el mapa
 * real de CR-BioLM lo reemplace, `descargarSvg` sigue sirviendo si el mapa es
 * SVG; si pasa a ser canvas o teselas (Leaflet, MapLibre), habrá que exportarlo
 * con la API propia de esa librería.
 */
import type { RespuestaConsulta } from "../types";

/** Fecha local en formato AAAA-MM-DD, para los nombres de archivo. */
function fechaCorta(fecha: Date): string {
  const dos = (n: number) => String(n).padStart(2, "0");
  return `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}-${dos(fecha.getDate())}`;
}

/** Nombre base común a los archivos de una misma respuesta. */
export function nombreBase(respuesta: RespuestaConsulta, fecha = new Date()): string {
  return `florabot-${respuesta.especie.id}-${fechaCorta(fecha)}`;
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
    "FloraBot CR — Resultado de consulta",
    `Descargado: ${fecha.toLocaleString("es-CR")}`,
    "",
    `Consulta: ${consulta}`,
    "",
    `Especie: ${especie.nombre_comun ?? "—"} (${especie.nombre_cientifico})`,
    `Familia: ${especie.familia}`,
  ];
  if (respuesta.elevacion) lineas.push(`Elevación: ${respuesta.elevacion}`);

  lineas.push("", respuesta.texto, "");

  if (respuesta.registros.length > 0) {
    lineas.push(`Registros de presencia (${respuesta.total_registros}):`);
    for (const r of respuesta.registros) {
      const elevacion = r.elevacion_m !== null ? `${r.elevacion_m} m` : "—";
      lineas.push(
        `- ${r.localidad} | ${r.fecha} | ${r.latitud.toFixed(4)}, ${r.longitud.toFixed(4)} | ${elevacion} | ${r.fuente}`,
      );
    }
    lineas.push("");
  }

  lineas.push(`Fuentes: ${respuesta.fuentes.join(", ")}`);

  // CRLF para que el Bloc de notas de Windows respete los saltos de línea.
  return lineas.join("\r\n");
}

/**
 * Serializa un elemento SVG del DOM a un archivo independiente.
 *
 * Se trabaja sobre una copia para fijar un tamaño explícito sin alterar el
 * mapa en pantalla, que usa clases de Tailwind que fuera de la página no
 * existen. XMLSerializer agrega el espacio de nombres SVG automáticamente.
 */
export function descargarSvg(svg: SVGSVGElement, nombre: string, ancho = 680, alto = 360): void {
  const copia = svg.cloneNode(true) as SVGSVGElement;
  copia.removeAttribute("class");
  copia.setAttribute("width", String(ancho));
  copia.setAttribute("height", String(alto));
  const contenido =
    '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(copia);
  descargarArchivo(nombre, contenido, "image/svg+xml;charset=utf-8");
}
