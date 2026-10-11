/**
 * Marco común de las pantallas de acceso: inicio de sesión, registro,
 * recuperación y restablecimiento de contraseña, y verificación de correo.
 *
 * Pone el fondo, el logo con el nombre de la aplicación y la tarjeta blanca;
 * cada pantalla solo aporta lo que va dentro de la tarjeta.
 */
import type { ReactNode } from "react";
import { Link } from "react-router";

import { NOMBRE_APP } from "../config/marca";
import { Logo } from "./Logo";

/** Enlaces al pie de las pantallas secundarias: volver a iniciar sesión o seguir sin cuenta. */
export function EnlacesAcceso() {
  return (
    <p className="text-center text-sm mt-5" style={{ color: "var(--color-texto-secundario)" }}>
      <Link to="/login" className="font-medium" style={{ color: "var(--color-texto-marca)" }}>
        Iniciar sesión
      </Link>
      {" · "}
      <Link to="/" className="font-medium" style={{ color: "var(--color-texto-marca)" }}>
        Continuar sin cuenta
      </Link>
    </p>
  );
}

export function PantallaAcceso({ subtitulo, children }: { subtitulo?: string; children: ReactNode }) {
  return (
    <div
      className="min-h-full flex items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, var(--color-superficie-marca) 0%, var(--color-fondo) 50%, var(--color-degradado) 100%)" }}
    >
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="mb-4">
            <Logo tamano={64} redondeo={16} />
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--color-texto)", fontFamily: "'Lora', serif" }}>
            {NOMBRE_APP}
          </h1>
          {subtitulo && (
            <p className="text-sm mt-1" style={{ color: "var(--color-texto-secundario)" }}>
              {subtitulo}
            </p>
          )}
        </div>

        <div
          className="rounded-2xl p-8"
          style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)", boxShadow: "var(--sombra-tarjeta)" }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
