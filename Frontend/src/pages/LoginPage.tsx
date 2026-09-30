/**
 * Inicio de sesión — RR_00_01.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const navigate = useNavigate();
  const { entrar, limpiarError, sesionExpirada, limpiarExpiracion } = useAuth();
  // RR_00_04: se recuerda el motivo para mostrarlo y se limpia del contexto,
  // así volver al agente sin iniciar sesión no redirige otra vez aquí.
  const [porInactividad] = useState(sesionExpirada);
  useEffect(() => {
    if (sesionExpirada) limpiarExpiracion();
  }, [sesionExpirada, limpiarExpiracion]);
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!correo || !password) {
      setError("Completa el correo y la contraseña.");
      return;
    }
    setError("");
    limpiarError();
    setCargando(true);
    try {
      await entrar(correo, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
    } finally {
      setCargando(false);
    }
  };

  const estiloCampo = {
    border: "1.5px solid #c5dccb",
    background: "#f7f8f5",
    color: "#1e3d2a",
  };

  return (
    <div
      className="min-h-full flex items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #e8f0eb 0%, #f7f8f5 50%, #d4e8da 100%)" }}
    >
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div
            className="flex items-center justify-center rounded-2xl mb-4"
            style={{ width: 64, height: 64, background: "#2d5a3d" }}
          >
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 2C8 2 5 6 5 10c0 3 1.5 5.5 4 7l1 4h4l1-4c2.5-1.5 4-4 4-7 0-4-3-8-7-8z" fill="white" opacity="0.9" />
              <path d="M12 6v10M9 9l3-3 3 3M9 13l3 3 3-3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "#1e3d2a", fontFamily: "'Lora', serif" }}>
            FloraBot CR
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6b8f74" }}>
            Consultas geoespaciales sobre flora de Costa Rica
          </p>
        </div>

        <div
          className="rounded-2xl p-8"
          style={{ background: "#ffffff", border: "1px solid #dde8df", boxShadow: "0 4px 24px rgba(45,90,61,0.08)" }}
        >
          <h2 className="text-lg font-semibold mb-6" style={{ color: "#1e3d2a" }}>
            Iniciar sesión
          </h2>

          {porInactividad && !error && (
            <div
              role="status"
              className="rounded-xl p-3.5 mb-5 text-sm"
              style={{ background: "#fff8e6", border: "1px solid #f3d58a", color: "#7a5a00" }}
            >
              Tu sesión se cerró por inactividad. Inicia sesión de nuevo para continuar.
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl p-3.5 mb-5 text-sm"
              style={{ background: "#fef3f2", border: "1px solid #fca5a5", color: "#991b1b" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="shrink-0 mt-0.5" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <span>
                {error}
                {/* RR_00_07 — cuenta sin verificar: se ofrece reenviar el enlace. */}
                {/verificar tu correo/i.test(error) && (
                  <Link
                    to="/verify-email"
                    state={{ correo }}
                    className="block font-medium underline mt-1"
                    style={{ color: "#991b1b" }}
                  >
                    Reenviar correo de verificación
                  </Link>
                )}
              </span>
            </div>
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
                className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
                style={estiloCampo}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "#2d5a3d";
                  e.currentTarget.style.background = "#fff";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = "#c5dccb";
                  e.currentTarget.style.background = "#f7f8f5";
                }}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="password" className="block text-sm font-medium" style={{ color: "#374a3c" }}>
                  Contraseña
                </label>
                <Link to="/forgot-password" className="text-xs" style={{ color: "#2d5a3d" }}>
                  ¿Olvidaste tu contraseña?
                </Link>
              </div>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
                style={estiloCampo}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "#2d5a3d";
                  e.currentTarget.style.background = "#fff";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = "#c5dccb";
                  e.currentTarget.style.background = "#f7f8f5";
                }}
              />
            </div>

            <button
              type="submit"
              disabled={cargando}
              className="w-full rounded-xl py-3 text-sm font-semibold mt-2 transition-all"
              style={{
                background: cargando ? "#a8d4b0" : "#2d5a3d",
                color: "#ffffff",
                border: "none",
                cursor: cargando ? "default" : "pointer",
              }}
            >
              {cargando ? "Verificando..." : "Iniciar sesión"}
            </button>
          </form>

          <div className="flex items-center gap-3 my-5">
            <div style={{ flex: 1, height: 1, background: "#dde8df" }} />
            <span className="text-xs" style={{ color: "#8aab92" }}>o</span>
            <div style={{ flex: 1, height: 1, background: "#dde8df" }} />
          </div>

          {/* RR_00_11 — se puede usar el agente sin cuenta. */}
          <button
            onClick={() => navigate("/")}
            className="w-full rounded-xl py-3 text-sm font-medium transition-all"
            style={{ background: "transparent", color: "#2d5a3d", border: "1.5px solid #c5dccb", cursor: "pointer" }}
          >
            Continuar sin cuenta
          </button>

          <p className="text-center text-sm mt-5" style={{ color: "#6b8f74" }}>
            ¿No tienes cuenta?{" "}
            <Link to="/register" className="font-medium" style={{ color: "#2d5a3d" }}>
              Regístrate
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
