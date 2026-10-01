/**
 * Marco común de las pantallas de acceso: inicio de sesión, registro,
 * recuperación y restablecimiento de contraseña, y verificación de correo.
 *
 * Pone el fondo, el logo con el nombre de la aplicación y la tarjeta blanca;
 * cada pantalla solo aporta lo que va dentro de la tarjeta.
 */
import type { ReactNode } from "react";
import { Link } from "react-router";

/** Enlaces al pie de las pantallas secundarias: volver a iniciar sesión o seguir sin cuenta. */
export function EnlacesAcceso() {
  return (
    <p className="text-center text-sm mt-5" style={{ color: "#6b8f74" }}>
      <Link to="/login" className="font-medium" style={{ color: "#2d5a3d" }}>
        Iniciar sesión
      </Link>
      {" · "}
      <Link to="/" className="font-medium" style={{ color: "#2d5a3d" }}>
        Continuar sin cuenta
      </Link>
    </p>
  );
}

export function PantallaAcceso({ subtitulo, children }: { subtitulo?: string; children: ReactNode }) {
  return (
    <div
      className="min-h-full flex items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #e8f0eb 0%, #f7f8f5 50%, #d4e8da 100%)" }}
    >
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center rounded-2xl mb-4" style={{ width: 64, height: 64, background: "#2d5a3d" }}>
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 2C8 2 5 6 5 10c0 3 1.5 5.5 4 7l1 4h4l1-4c2.5-1.5 4-4 4-7 0-4-3-8-7-8z" fill="white" opacity="0.9" />
              <path d="M12 6v10M9 9l3-3 3 3M9 13l3 3 3-3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "#1e3d2a", fontFamily: "'Lora', serif" }}>
            FloraBot CR
          </h1>
          {subtitulo && (
            <p className="text-sm mt-1" style={{ color: "#6b8f74" }}>
              {subtitulo}
            </p>
          )}
        </div>

        <div
          className="rounded-2xl p-8"
          style={{ background: "#ffffff", border: "1px solid #dde8df", boxShadow: "0 4px 24px rgba(45,90,61,0.08)" }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
