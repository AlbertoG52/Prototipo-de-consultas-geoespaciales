/**
 * Logo de la aplicación.
 *
 * Muestra el archivo de LOGO_URL (config/marca.ts), que vive en public/. Para
 * usar el logo del cliente basta con reemplazar ese archivo: todas las
 * pantallas que muestran el logo usan este componente.
 */
import { LOGO_URL } from "../config/marca";

export function Logo({ tamano, redondeo }: { tamano: number; redondeo: number }) {
  return (
    <img
      src={LOGO_URL}
      alt=""
      aria-hidden="true"
      width={tamano}
      height={tamano}
      className="shrink-0"
      style={{ display: "block", borderRadius: redondeo }}
    />
  );
}
