/**
 * Recuperación de contraseña, paso 2 — RR_00_06 criterio 3.
 *
 * Se llega desde el enlace del correo (/reset-password?token=...). El servidor
 * valida el token al guardar: si venció o ya se usó, se ofrece pedir otro.
 * Las reglas de la contraseña son las mismas del registro (RR_00_03).
 */
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import * as api from "../services/api";
import { FuerzaContrasena, REGLAS } from "./RegisterPage";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [parametros] = useSearchParams();
  const token = parametros.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [error, setError] = useState("");
  // El enlace no sirve (no existe, venció o ya se usó): hay que pedir otro.
  const [enlaceInvalido, setEnlaceInvalido] = useState(!token);
  const [listo, setListo] = useState("");
  const [cargando, setCargando] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    const faltantes = REGLAS.filter((r) => !r.cumple(password));
    if (faltantes.length) {
      setError(`La contraseña no cumple: ${faltantes.map((r) => r.etiqueta.toLowerCase()).join(", ")}.`);
      return;
    }
    if (password !== confirmar) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setError("");
    setCargando(true);
    try {
      const r = await api.restablecerPassword(token, password);
      setListo(r.mensaje);
    } catch (err) {
      if (err instanceof api.ErrorApi) {
        if (err.status === 400) setEnlaceInvalido(true);
        setError(err.message);
      } else {
        setError("No se pudo conectar con el servidor. Intenta de nuevo.");
      }
    } finally {
      setCargando(false);
    }
  };

  const estiloCampo = { border: "1.5px solid #c5dccb", background: "#f7f8f5", color: "#1e3d2a" };
  const botonPrincipal = { background: "#2d5a3d", color: "#ffffff", border: "none", cursor: "pointer" } as const;

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
          <h2 className="text-lg font-semibold text-center mb-2" style={{ color: "#1e3d2a" }}>
            {listo ? "Contraseña actualizada" : "Elige una contraseña nueva"}
          </h2>

          {listo ? (
            <>
              <p role="status" className="text-sm text-center mb-6" style={{ color: "#6b8f74" }}>
                {listo}
              </p>
              <button onClick={() => navigate("/login")} className="w-full rounded-xl py-3 text-sm font-semibold" style={botonPrincipal}>
                Iniciar sesión
              </button>
            </>
          ) : enlaceInvalido ? (
            <>
              <p role="alert" className="text-sm text-center mb-6" style={{ color: "#991b1b" }}>
                {error || "Este enlace no es válido. Pide uno nuevo para cambiar tu contraseña."}
              </p>
              <button onClick={() => navigate("/forgot-password")} className="w-full rounded-xl py-3 text-sm font-semibold" style={botonPrincipal}>
                Pedir un enlace nuevo
              </button>
            </>
          ) : (
            <form onSubmit={enviar} className="flex flex-col gap-4 mt-4">
              {error && (
                <p role="alert" className="text-sm rounded-xl p-3" style={{ background: "#fef3f2", border: "1px solid #fca5a5", color: "#991b1b" }}>
                  {error}
                </p>
              )}
              <div>
                <label htmlFor="password" className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>
                  Contraseña nueva
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                  style={estiloCampo}
                />
                <FuerzaContrasena password={password} />
              </div>
              <div>
                <label htmlFor="confirmar" className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>
                  Confirmar contraseña
                </label>
                <input
                  id="confirmar"
                  type="password"
                  autoComplete="new-password"
                  value={confirmar}
                  onChange={(e) => setConfirmar(e.target.value)}
                  className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                  style={estiloCampo}
                />
              </div>
              <button
                type="submit"
                disabled={cargando}
                className="w-full rounded-xl py-3 text-sm font-semibold"
                style={{ ...botonPrincipal, background: cargando ? "#a8d4b0" : "#2d5a3d", cursor: cargando ? "default" : "pointer" }}
              >
                {cargando ? "Guardando..." : "Guardar contraseña"}
              </button>
            </form>
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
