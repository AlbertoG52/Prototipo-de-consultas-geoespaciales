/**
 * Recuperación de contraseña, paso 1 — RR_00_06 criterios 1 y 2.
 *
 * La persona escribe su correo registrado y recibe un enlace que vence en 30
 * minutos. La respuesta es la misma exista o no la cuenta, para no revelar qué
 * correos están registrados. El paso 2 es ResetPasswordPage.
 */
import { useState } from "react";
import { useNavigate } from "react-router";

import { Mail } from "lucide-react";
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
        <div className="rounded-full p-3" style={{ background: "var(--color-superficie-marca)" }}>
          <Mail size={28} strokeWidth={1.8} style={{ color: "var(--color-texto-marca)" }} />
        </div>
      </div>

      <h2 className="text-lg font-semibold text-center mb-2" style={{ color: "var(--color-texto)" }}>
        Recuperar contraseña
      </h2>

      {enviado ? (
        <>
          <p role="status" className="text-sm text-center mb-6" style={{ color: "var(--color-texto-secundario)" }}>
            {enviado} Ábrelo en esta misma computadora.
          </p>
          <BotonPrincipal onClick={() => navigate("/login")}>Volver al inicio de sesión</BotonPrincipal>
          <button
            onClick={() => setEnviado("")}
            className="w-full text-xs mt-3"
            style={{ background: "transparent", color: "var(--color-texto-marca)", border: "none", cursor: "pointer" }}
          >
            ¿No te llegó? Pedir otro enlace
          </button>
        </>
      ) : (
        <>
          <p className="text-sm text-center mb-6" style={{ color: "var(--color-texto-secundario)" }}>
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
