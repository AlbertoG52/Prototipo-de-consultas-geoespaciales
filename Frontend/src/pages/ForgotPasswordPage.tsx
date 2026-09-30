/**
 * Recuperación de contraseña, paso 1 — RR_00_06 criterios 1 y 2.
 *
 * La persona escribe su correo registrado y recibe un enlace que vence en 30
 * minutos. La respuesta es la misma exista o no la cuenta, para no revelar qué
 * correos están registrados. El paso 2 es ResetPasswordPage.
 */
import { useState } from "react";
import { Link, useNavigate } from "react-router";

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
        </div>

        <div
          className="rounded-2xl p-8"
          style={{ background: "#ffffff", border: "1px solid #dde8df", boxShadow: "0 4px 24px rgba(45,90,61,0.08)" }}
        >
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
              <button
                onClick={() => navigate("/login")}
                className="w-full rounded-xl py-3 text-sm font-semibold"
                style={{ background: "#2d5a3d", color: "#ffffff", border: "none", cursor: "pointer" }}
              >
                Volver al inicio de sesión
              </button>
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

              {error && (
                <p role="alert" className="text-sm rounded-xl p-3 mb-4" style={{ background: "#fef3f2", border: "1px solid #fca5a5", color: "#991b1b" }}>
                  {error}
                </p>
              )}

              <form onSubmit={enviar} className="flex flex-col gap-4">
                <div>
                  <label htmlFor="correo" className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>
                    Correo electrónico
                  </label>
                  <input
                    id="correo"
                    type="email"
                    autoComplete="email"
                    value={correo}
                    onChange={(e) => setCorreo(e.target.value)}
                    placeholder="tu@correo.com"
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                    style={{ border: "1.5px solid #c5dccb", background: "#f7f8f5", color: "#1e3d2a" }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={cargando}
                  className="w-full rounded-xl py-3 text-sm font-semibold"
                  style={{
                    background: cargando ? "#a8d4b0" : "#2d5a3d",
                    color: "#ffffff",
                    border: "none",
                    cursor: cargando ? "default" : "pointer",
                  }}
                >
                  {cargando ? "Enviando..." : "Enviar enlace"}
                </button>
              </form>
            </>
          )}

          <p className="text-center text-sm mt-5" style={{ color: "#6b8f74" }}>
            <Link to="/login" className="font-medium" style={{ color: "#2d5a3d" }}>
              Iniciar sesión
            </Link>
            {" · "}
            <Link to="/" className="font-medium" style={{ color: "#2d5a3d" }}>
              Continuar sin cuenta
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
