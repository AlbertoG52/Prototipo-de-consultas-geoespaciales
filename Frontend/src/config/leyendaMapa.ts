/**
 * RR_48 — qué significa cada símbolo del mapa de CR-BioLM.
 *
 * El PNG trae su propia leyenda, pero al hacer zoom se agranda con todo el
 * mapa y queda cortada. Esta leyenda se dibuja aparte, encima del mapa, para
 * que se vea siempre (criterio 3).
 *
 * Los colores y la forma de cada símbolo copian la leyenda que trae el PNG de
 * CR-BioLM (revisada con el mapa real de Quercus costaricensis). Si José cambia
 * los colores o las capas del mapa, hay que actualizar esta lista.
 */

export type SimboloLeyenda = {
  /** Color de relleno del símbolo. */
  color: string;
  /** Qué representa en el mapa. */
  etiqueta: string;
  /** Rayado: los registros atípicos se dibujan con líneas diagonales. */
  rayado?: boolean;
  /** Borde del símbolo, cuando el relleno es muy parecido al fondo del mapa. */
  borde?: string;
  /** Solo el contorno, sin relleno (la zona geográfica y las áreas protegidas). */
  contorno?: boolean;
  /** Color del contorno sobre fondo claro, si el original no se ve (el blanco). */
  contornoEnClaro?: string;
  /** Contorno discontinuo (la región inferida a partir de GBIF). */
  discontinuo?: boolean;
  /** Los registros de GBIF: la leyenda agrega cuántos hay en el mapa. */
  registros?: boolean;
};

export const LEYENDA_MAPA: SimboloLeyenda[] = [
  { color: "#22d3ee", etiqueta: "Hábitat óptimo: dentro del rango de elevación de la especie" },
  { color: "#22d3ee", etiqueta: "Registros atípicos: fuera del rango de elevación habitual", rayado: true },
  { color: "#ffffff", etiqueta: "Zona geográfica de la especie (contorno blanco)", contorno: true, contornoEnClaro: "#6b7280" },
  { color: "#2e3440", etiqueta: "Fuera del rango geográfico de la especie", borde: "#4c566a" },
  { color: "#ff4444", etiqueta: "Registros de presencia de GBIF", registros: true },
  {
    color: "#f59e0b",
    etiqueta: "Región inferida por registros de GBIF (contorno discontinuo)",
    contorno: true,
    discontinuo: true,
  },
  { color: "#d4a72c", etiqueta: "Áreas silvestres protegidas (SINAC, contorno amarillo)", contorno: true },
];

/**
 * Las regiones botánicas tienen un color cada una y cambian según la especie;
 * sus nombres (y la vertiente) los pone CR-BioLM en el recuadro izquierdo del mapa.
 */
export const NOTA_REGIONES =
  "Cada región botánica donde crece la especie tiene su propio color; sus nombres y la vertiente están en el recuadro inferior izquierdo del mapa.";
