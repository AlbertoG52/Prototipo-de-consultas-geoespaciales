/**
 * Creación de cuenta — RR_00_01 criterio 1.
 *
 * Las reglas de contraseña que se muestran mientras el usuario escribe son las
 * mismas que valida el servidor (app/schemas/usuario.py). La comprobación del
 * navegador es una ayuda para quien escribe, el servidor
 * rechaza igual una contraseña débil aunque alguien salte esta pantalla.
 *
 */
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../context/AuthContext";

/** Mismas reglas que valida el backend. */
const REGLAS = [
  { etiqueta: "Al menos 8 caracteres", cumple: (p: string) => p.length >= 8 },
  { etiqueta: "Una letra mayúscula", cumple: (p: string) => /[A-Z]/.test(p) },
  { etiqueta: "Un número", cumple: (p: string) => /\d/.test(p) },
  { etiqueta: "Un carácter especial (!@#$%^&*)", cumple: (p: string) => /[!@#$%^&*]/.test(p) },
];

function FuerzaContrasena({ password }: { password: string }) {
  const puntaje = REGLAS.filter((r) => r.cumple(password)).length;
  const colores = ["#c5dccb", "#f59e0b", "#f59e0b", "#22c55e", "#2d5a3d"];
  const etiquetas = ["", "Débil", "Regular", "Buena", "Fuerte"];

  return (
    <div className="mt-2">
      <div className="flex gap-1 mb-1.5">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex-1 rounded-full"
            style={{ height: 4, background: i < puntaje ? colores[puntaje] : "#e8f0eb", transition: "background 0.3s" }}
          />
        ))}
      </div>
      {password && (
        <p className="text-xs mb-2" style={{ color: colores[puntaje] }}>
          {etiquetas[puntaje]}
        </p>
      )}
      <div className="flex flex-col gap-0.5">
        {REGLAS.map((r) => {
          const ok = r.cumple(password);
          return (
            <div key={r.etiqueta} className="flex items-center gap-1.5 text-xs" style={{ color: ok ? "#2d5a3d" : "#8aab92" }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                {ok ? (
                  <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                ) : (
                  <circle cx="12" cy="12" r="4" fill="currentColor" opacity="0.3" />
                )}
              </svg>
              {r.etiqueta}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { registrarse } = useAuth();
  const [form, setForm] = useState({ nombre: "", correo: "", password: "", confirmar: "" });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [errorGeneral, setErrorGeneral] = useState("");
  const [cargando, setCargando] = useState(false);

  const validar = () => {
    const e: Record<string, string> = {};
    if (!form.nombre.trim()) e.nombre = "El nombre es requerido.";
    if (!form.correo.includes("@")) e.correo = "Ingresa un correo válido.";
    const faltantes = REGLAS.filter((r) => !r.cumple(form.password));
    if (faltantes.length) e.password = "La contraseña no cumple todos los requisitos.";
    if (form.password !== form.confirmar) e.confirmar = "Las contraseñas no coinciden.";
    return e;
  };

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    const encontrados = validar();
    setErrores(encontrados);
    if (Object.keys(encontrados).length) return;

    setErrorGeneral("");
    setCargando(true);
    try {
      await registrarse(form.nombre, form.correo, form.password);
      navigate("/login", { state: { registrado: true } });
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo crear la cuenta.");
    } finally {
      setCargando(false);
    }
  };

  const campo = (
    clave: keyof typeof form,
    etiqueta: string,
    tipo = "text",
    marcador = "",
    autoComplete?: string,
  ) => (
    <div>
      <label htmlFor={clave} className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>
        {etiqueta}
      </label>
      <input
        id={clave}
        type={tipo}
        autoComplete={autoComplete}
        value={form[clave]}
        onChange={(e) => setForm((f) => ({ ...f, [clave]: e.target.value }))}
        placeholder={marcador}
        className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
        style={{
          border: `1.5px solid ${errores[clave] ? "#fca5a5" : "#c5dccb"}`,
          background: "#f7f8f5",
          color: "#1e3d2a",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "#2d5a3d";
          e.currentTarget.style.background = "#fff";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = errores[clave] ? "#fca5a5" : "#c5dccb";
          e.currentTarget.style.background = "#f7f8f5";
        }}
      />
      {errores[clave] && (
        <p className="text-xs mt-1" style={{ color: "#dc2626" }}>
          {errores[clave]}
        </p>
      )}
    </div>
  );

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
          <p className="text-sm mt-1" style={{ color: "#6b8f74" }}>
            Crea tu cuenta para comenzar
          </p>
        </div>

        <div
          className="rounded-2xl p-8"
          style={{ background: "#ffffff", border: "1px solid #dde8df", boxShadow: "0 4px 24px rgba(45,90,61,0.08)" }}
        >
          <h2 className="text-lg font-semibold mb-6" style={{ color: "#1e3d2a" }}>
            Crear cuenta
          </h2>

          {errorGeneral && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl p-3.5 mb-5 text-sm"
              style={{ background: "#fef3f2", border: "1px solid #fca5a5", color: "#991b1b" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="shrink-0 mt-0.5" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              {errorGeneral}
            </div>
          )}

          <form onSubmit={enviar} className="flex flex-col gap-4">
            {campo("nombre", "Nombre completo", "text", "Juan Pérez", "name")}
            {campo("correo", "Correo electrónico", "email", "tu@correo.com", "email")}

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="••••••••"
                className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
                style={{
                  border: `1.5px solid ${errores.password ? "#fca5a5" : "#c5dccb"}`,
                  background: "#f7f8f5",
                  color: "#1e3d2a",
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "#2d5a3d";
                  e.currentTarget.style.background = "#fff";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = errores.password ? "#fca5a5" : "#c5dccb";
                  e.currentTarget.style.background = "#f7f8f5";
                }}
              />
              {errores.password && (
                <p className="text-xs mt-1" style={{ color: "#dc2626" }}>
                  {errores.password}
                </p>
              )}
              {form.password && <FuerzaContrasena password={form.password} />}
            </div>

            {campo("confirmar", "Confirmar contraseña", "password", "••••••••", "new-password")}

            <p className="text-xs" style={{ color: "#8aab92" }}>
              Al registrarte se te asignará el rol de{" "}
              <strong style={{ color: "#2d5a3d" }}>usuario estándar</strong>, con más consultas
              diarias que las disponibles sin cuenta.
            </p>

            <button
              type="submit"
              disabled={cargando}
              className="w-full rounded-xl py-3 text-sm font-semibold mt-1 transition-all"
              style={{
                background: cargando ? "#a8d4b0" : "#2d5a3d",
                color: "#ffffff",
                border: "none",
                cursor: cargando ? "default" : "pointer",
              }}
            >
              {cargando ? "Creando cuenta..." : "Crear cuenta"}
            </button>
          </form>

          <p className="text-center text-sm mt-5" style={{ color: "#6b8f74" }}>
            ¿Ya tienes cuenta?{" "}
            <Link to="/login" className="font-medium" style={{ color: "#2d5a3d" }}>
              Inicia sesión
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
