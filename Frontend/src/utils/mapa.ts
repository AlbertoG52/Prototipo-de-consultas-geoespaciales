/**
 * Coherencia entre el mapa y la especie.
 *
 * El backend arma la `url` del mapa con el id de la especie (GET /especies/{id}/mapa). Antes de
 * mostrar un mapa se comprueba que sea el de la especie de la respuesta o de la ficha; si no
 * coincide, no se muestra ninguno.
 */
import type { MapaEspecie } from "../types";

/** Ruta del PNG del mapa de una especie, tal como la arma el backend. */
export function rutaDelMapa(especieId: string): string {
  return `/especies/${especieId}/mapa`;
}

/**
 * true si `mapa` existe y es el de `especieId`. Se llama en cada respuesta y en cada ficha, antes
 * de mostrar el mapa.
 */
export function mapaDeLaEspecie(mapa: MapaEspecie | null, especieId: string): mapa is MapaEspecie {
  return mapa !== null && mapa.url === rutaDelMapa(especieId);
}
