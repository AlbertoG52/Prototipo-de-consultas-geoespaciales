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
import { useLocation, useNavigate, useSearchParams } from "react-router";

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { EnlacesAcceso, PantallaAcceso } from "../components/PantallaAcceso";
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

  return (
    <PantallaAcceso>
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
          <BotonPrincipal onClick={() => navigate("/login")}>Iniciar sesión</BotonPrincipal>
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
            <CampoTexto
              etiqueta="¿No te llegó? Te lo reenviamos"
              tipo="email"
              autoComplete="email"
              valor={correo}
              onCambiar={setCorreo}
              marcador="tu@correo.com"
            />
            <BotonPrincipal tipo="submit" deshabilitado={enviando}>
              {enviando ? "Enviando..." : "Reenviar correo de verificación"}
            </BotonPrincipal>
          </form>

          {aviso && <Aviso tipo="exito" className="mt-4">{aviso}</Aviso>}

          <EnlacesAcceso />
        </>
      )}
    </PantallaAcceso>
  );
}
