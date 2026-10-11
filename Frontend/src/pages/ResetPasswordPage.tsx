/**
 * Recuperación de contraseña, paso 2 — RR_00_06 criterio 3.
 *
 * Se llega desde el enlace del correo (/reset-password?token=...). El servidor
 * valida el token al guardar: si venció o ya se usó, se ofrece pedir otro.
 * Las reglas de la contraseña son las mismas del registro (RR_00_03).
 */
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { FuerzaContrasena, REGLAS_PASSWORD } from "../components/FuerzaContrasena";
import { EnlacesAcceso, PantallaAcceso } from "../components/PantallaAcceso";
import * as api from "../services/api";

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
    const faltantes = REGLAS_PASSWORD.filter((r) => !r.cumple(password));
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

  return (
    <PantallaAcceso>
      <h2 className="text-lg font-semibold text-center mb-2" style={{ color: "var(--color-texto)" }}>
        {listo ? "Contraseña actualizada" : "Elige una contraseña nueva"}
      </h2>

      {listo ? (
        <>
          <p role="status" className="text-sm text-center mb-6" style={{ color: "var(--color-texto-secundario)" }}>
            {listo}
          </p>
          <BotonPrincipal onClick={() => navigate("/login")}>Iniciar sesión</BotonPrincipal>
        </>
      ) : enlaceInvalido ? (
        <>
          <p role="alert" className="text-sm text-center mb-6" style={{ color: "var(--color-error-texto)" }}>
            {error || "Este enlace no es válido. Pide uno nuevo para cambiar tu contraseña."}
          </p>
          <BotonPrincipal onClick={() => navigate("/forgot-password")}>Pedir un enlace nuevo</BotonPrincipal>
        </>
      ) : (
        <form onSubmit={enviar} className="flex flex-col gap-4 mt-4">
          {error && <Aviso tipo="error" className="">{error}</Aviso>}
          <CampoTexto
            etiqueta="Contraseña nueva"
            tipo="password"
            autoComplete="new-password"
            valor={password}
            onCambiar={setPassword}
          >
            <FuerzaContrasena password={password} />
          </CampoTexto>
          <CampoTexto
            etiqueta="Confirmar contraseña"
            tipo="password"
            autoComplete="new-password"
            valor={confirmar}
            onCambiar={setConfirmar}
          />
          <BotonPrincipal tipo="submit" deshabilitado={cargando}>
            {cargando ? "Guardando..." : "Guardar contraseña"}
          </BotonPrincipal>
        </form>
      )}

      <EnlacesAcceso />
    </PantallaAcceso>
  );
}
