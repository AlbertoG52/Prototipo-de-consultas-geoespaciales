/**
 * Recuperación de contraseña, paso 1 — RR_00_06 criterios 1 y 2.
 *
 * La persona escribe su correo registrado y recibe un enlace que vence en 30
 * minutos. La respuesta es la misma exista o no la cuenta, para no revelar qué
 * correos están registrados. El paso 2 es ResetPasswordPage.
 */
import { useState } from "react";
import { useNavigate } from "react-router";

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { EnlacesAcceso, PantallaAcceso } from "../components/PantallaAcceso";
import * as api from "../services/api";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [correo, setCorreo] = useState("");
  const [error, setError] = useState("");
  const [enviado, setEnviado] = useState("");
  const [cargando, setCargando] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!correo.includes("@")) {
      setError("Ingresa el correo con el que te registraste.");
      return;
    }
    setError("");
    setCargando(true);
    try {
      const r = await api.solicitarRecuperacion(correo.trim());
      setEnviado(r.mensaje);
    } catch (err) {
      setError(err instanceof api.ErrorApi ? err.message : "No se pudo conectar con el servidor. Intenta de nuevo.");
    } finally {
      setCargando(false);
    }
  };

  return (
    <PantallaAcceso>
      <div className="flex items-center justify-center mb-5">
        <div className="rounded-full p-3" style={{ background: "#e8f0eb" }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="2" y="4" width="20" height="16" rx="2" stroke="#2d5a3d" strokeWidth="1.8" />
            <path d="M2 8l10 6 10-6" stroke="#2d5a3d" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </div>
      </div>

      <h2 className="text-lg font-semibold text-center mb-2" style={{ color: "#1e3d2a" }}>
        Recuperar contraseña
      </h2>

      {enviado ? (
        <>
          <p role="status" className="text-sm text-center mb-6" style={{ color: "#6b8f74" }}>
            {enviado} Ábrelo en esta misma computadora.
          </p>
          <BotonPrincipal onClick={() => navigate("/login")}>Volver al inicio de sesión</BotonPrincipal>
          <button
            onClick={() => setEnviado("")}
            className="w-full text-xs mt-3"
            style={{ background: "transparent", color: "#2d5a3d", border: "none", cursor: "pointer" }}
          >
            ¿No te llegó? Pedir otro enlace
          </button>
        </>
      ) : (
        <>
          <p className="text-sm text-center mb-6" style={{ color: "#6b8f74" }}>
            Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una contraseña nueva.
          </p>

          {error && <Aviso tipo="error" className="mb-4">{error}</Aviso>}

          <form onSubmit={enviar} className="flex flex-col gap-4">
            <CampoTexto
              etiqueta="Correo electrónico"
              tipo="email"
              autoComplete="email"
              valor={correo}
              onCambiar={setCorreo}
              marcador="tu@correo.com"
            />
            <BotonPrincipal tipo="submit" deshabilitado={cargando}>
              {cargando ? "Enviando..." : "Enviar enlace"}
            </BotonPrincipal>
          </form>
        </>
      )}

      <EnlacesAcceso />
    </PantallaAcceso>
  );
}
