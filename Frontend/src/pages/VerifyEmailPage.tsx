/**
 * Verificación de correo — RR_00_07.
 *
 * Dos formas de llegar:
 *  - Desde el enlace del correo (/verify-email?token=...): se valida el token
 *    y la cuenta queda habilitada (criterio 3).
 *  - Después de registrarse o de un login rechazado por falta de verificación:
 *    se pide revisar el correo y se ofrece reenviar el enlace.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";

import * as api from "../services/api";

type Estado =
  | { fase: "verificando" }
  | { fase: "verificado"; mensaje: string }
  | { fase: "fallido"; mensaje: string }
  | { fase: "pendiente" };

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const [parametros] = useSearchParams();
  const token = parametros.get("token");
  // El correo llega por el estado de la navegación, no por la URL.
  const { state } = useLocation() as { state: { correo?: string; mensaje?: string } | null };

  const [estado, setEstado] = useState<Estado>(token ? { fase: "verificando" } : { fase: "pendiente" });
  const [correo, setCorreo] = useState(state?.correo ?? "");
  const [aviso, setAviso] = useState(state?.mensaje ?? "");
  const [enviando, setEnviando] = useState(false);

  // El token es de un solo uso: en desarrollo StrictMode monta el efecto dos
  // veces, y la segunda llamada lo encontraría ya usado.
  const yaEnviado = useRef(false);
  useEffect(() => {
    if (!token || yaEnviado.current) return;
    yaEnviado.current = true;
    api
      .verificarCorreo(token)
      .then((r) => setEstado({ fase: "verificado", mensaje: r.mensaje }))
      .catch((err) =>
        setEstado({
          fase: "fallido",
          mensaje: err instanceof api.ErrorApi ? err.message : "No se pudo conectar con el servidor.",
        }),
      );
  }, [token]);

  const reenviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!correo.includes("@")) {
      setAviso("Ingresa el correo con el que te registraste.");
      return;
    }
    setEnviando(true);
    try {
      const r = await api.reenviarVerificacion(correo.trim());
      setAviso(r.mensaje);
    } catch (err) {
      setAviso(err instanceof Error ? err.message : "No se pudo reenviar el correo.");
    } finally {
      setEnviando(false);
    }
  };

  const titulo = {
    verificando: "Verificando tu correo…",
    verificado: "Correo verificado",
    fallido: "No se pudo verificar",
    pendiente: "Verifica tu correo",
  }[estado.fase];

  const botonPrincipal = {
    width: "100%",
    background: "#2d5a3d",
    color: "#ffffff",
    border: "none",
    cursor: "pointer",
  } as const;

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
            <div className="rounded-full p-3" style={{ background: estado.fase === "fallido" ? "#fef3f2" : "#e8f0eb" }}>
              {estado.fase === "verificado" ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" stroke="#2d5a3d" strokeWidth="1.8" />
                  <path d="M8 12.5l2.5 2.5L16 9.5" stroke="#2d5a3d" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="2" y="4" width="20" height="16" rx="2" stroke={estado.fase === "fallido" ? "#dc2626" : "#2d5a3d"} strokeWidth="1.8" />
                  <path d="M2 8l10 6 10-6" stroke={estado.fase === "fallido" ? "#dc2626" : "#2d5a3d"} strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              )}
            </div>
          </div>

          <h2 className="text-lg font-semibold text-center mb-2" style={{ color: "#1e3d2a" }}>
            {titulo}
          </h2>

          {estado.fase === "verificando" && (
            <p role="status" className="text-sm text-center" style={{ color: "#6b8f74" }}>
              Un momento, estamos validando el enlace.
            </p>
          )}

          {estado.fase === "verificado" && (
            <>
              <p role="status" className="text-sm text-center mb-6" style={{ color: "#6b8f74" }}>
                {estado.mensaje}
              </p>
              <button onClick={() => navigate("/login")} className="rounded-xl py-3 text-sm font-semibold" style={botonPrincipal}>
                Iniciar sesión
              </button>
            </>
          )}

          {(estado.fase === "pendiente" || estado.fase === "fallido") && (
            <>
              <p
                role={estado.fase === "fallido" ? "alert" : undefined}
                className="text-sm text-center mb-5"
                style={{ color: estado.fase === "fallido" ? "#991b1b" : "#6b8f74" }}
              >
                {estado.fase === "fallido"
                  ? estado.mensaje
                  : "Te enviamos un enlace para activar tu cuenta. Ábrelo en esta misma computadora. Si no lo ves, revisa la carpeta de spam."}
              </p>
              <p className="text-xs text-center mb-5" style={{ color: "#8aab92" }}>
                Mientras tanto puedes seguir usando el agente sin cuenta.
              </p>

              {/* RR_00_07 — pedir un enlace nuevo; el anterior deja de servir. */}
              <form onSubmit={reenviar} className="flex flex-col gap-3">
                <label htmlFor="correo" className="text-sm font-medium" style={{ color: "#374a3c" }}>
                  ¿No te llegó? Te lo reenviamos
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
                <button
                  type="submit"
                  disabled={enviando}
                  className="rounded-xl py-3 text-sm font-semibold"
                  style={{ ...botonPrincipal, background: enviando ? "#a8d4b0" : "#2d5a3d", cursor: enviando ? "default" : "pointer" }}
                >
                  {enviando ? "Enviando..." : "Reenviar correo de verificación"}
                </button>
              </form>

              {aviso && (
                <p role="status" className="text-sm text-center mt-4 rounded-xl p-3" style={{ background: "#f0f5f1", color: "#2d5a3d" }}>
                  {aviso}
                </p>
              )}

              <p className="text-center text-sm mt-5" style={{ color: "#6b8f74" }}>
                <Link to="/login" className="font-medium" style={{ color: "#2d5a3d" }}>
                  Ir a iniciar sesión
                </Link>
                {" · "}
                <Link to="/" className="font-medium" style={{ color: "#2d5a3d" }}>
                  Continuar sin cuenta
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
