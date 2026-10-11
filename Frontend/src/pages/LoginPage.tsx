/**
 * Inicio de sesión — RR_00_01.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { PantallaAcceso } from "../components/PantallaAcceso";
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

  return (
    <PantallaAcceso subtitulo="Consultas geoespaciales sobre flora de Costa Rica">
      <h2 className="text-lg font-semibold mb-6" style={{ color: "var(--color-texto)" }}>
        Iniciar sesión
      </h2>

      {porInactividad && !error && (
        <Aviso tipo="advertencia">Tu sesión se cerró por inactividad. Inicia sesión de nuevo para continuar.</Aviso>
      )}

      {error && (
        <Aviso tipo="error">
          {error}
          {/* RR_00_07 — cuenta sin verificar: se ofrece reenviar el enlace. */}
          {/verificar tu correo/i.test(error) && (
            <Link
              to="/verify-email"
              state={{ correo }}
              className="block font-medium underline mt-1"
              style={{ color: "var(--color-error-texto)" }}
            >
              Reenviar correo de verificación
            </Link>
          )}
        </Aviso>
      )}

      <form onSubmit={enviar} className="flex flex-col gap-4">
        <CampoTexto
          etiqueta="Correo electrónico"
          tipo="email"
          autoComplete="email"
          valor={correo}
          onCambiar={setCorreo}
          marcador="tu@correo.com"
        />
        <CampoTexto
          etiqueta="Contraseña"
          tipo="password"
          autoComplete="current-password"
          valor={password}
          onCambiar={setPassword}
          marcador="••••••••"
          accion={
            <Link to="/forgot-password" className="text-xs" style={{ color: "var(--color-texto-marca)" }}>
              ¿Olvidaste tu contraseña?
            </Link>
          }
        />
        <BotonPrincipal tipo="submit" deshabilitado={cargando}>
          {cargando ? "Verificando..." : "Iniciar sesión"}
        </BotonPrincipal>
      </form>

      <div className="flex items-center gap-3 my-5">
        <div style={{ flex: 1, height: 1, background: "var(--color-borde)" }} />
        <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>o</span>
        <div style={{ flex: 1, height: 1, background: "var(--color-borde)" }} />
      </div>

      {/* RR_00_11 — se puede usar el agente sin cuenta. */}
      <button
        onClick={() => navigate("/")}
        className="w-full rounded-xl py-3 text-sm font-medium transition-all"
        style={{ background: "transparent", color: "var(--color-texto-marca)", border: "1.5px solid var(--color-borde-fuerte)", cursor: "pointer" }}
      >
        Continuar sin cuenta
      </button>

      <p className="text-center text-sm mt-5" style={{ color: "var(--color-texto-secundario)" }}>
        ¿No tienes cuenta?{" "}
        <Link to="/register" className="font-medium" style={{ color: "var(--color-texto-marca)" }}>
          Regístrate
        </Link>
      </p>
    </PantallaAcceso>
  );
}
