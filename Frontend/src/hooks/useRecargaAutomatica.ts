/**
 * Recarga periódica de datos que cambian solos (RR_78 criterio 3).
 *
 * Llama a `cargar` al montar el componente, cada `milisegundos` mientras la
 * pestaña del navegador está visible, y al volver a ella. Con la pestaña en
 * segundo plano no pide nada. Se detiene al desmontar el componente, así que
 * solo corre mientras se ve la sección que lo usa.
 *
 * `cargar` debe ser estable (useCallback): si cambia, el ciclo vuelve a empezar.
 */
import { useEffect } from "react";

export function useRecargaAutomatica(cargar: () => void, milisegundos: number) {
  useEffect(() => {
    cargar();
    const siEstaVisible = () => {
      if (!document.hidden) cargar();
    };
    const intervalo = window.setInterval(siEstaVisible, milisegundos);
    document.addEventListener("visibilitychange", siEstaVisible);
    return () => {
      window.clearInterval(intervalo);
      document.removeEventListener("visibilitychange", siEstaVisible);
    };
  }, [cargar, milisegundos]);
}
