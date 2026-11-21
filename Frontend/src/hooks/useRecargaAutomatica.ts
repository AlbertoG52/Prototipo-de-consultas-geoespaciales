/**
 * Recarga periódica de datos que cambian solos.
 *
 * Llama a `cargar` al montar el componente, cada `milisegundos` mientras la pestaña está visible y
 * al volver a ella. Se detiene al desmontar el componente. `cargar` debe ser estable (useCallback):
 * si cambia, el ciclo vuelve a empezar.
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
