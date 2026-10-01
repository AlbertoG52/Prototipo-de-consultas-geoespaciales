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

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { FuerzaContrasena, REGLAS_PASSWORD } from "../components/FuerzaContrasena";
import { PantallaAcceso } from "../components/PantallaAcceso";
import { useAuth } from "../context/AuthContext";

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
    const faltantes = REGLAS_PASSWORD.filter((r) => !r.cumple(form.password));
    // RR_00_03 criterio 2: se indica el motivo concreto, no solo que falla.
    if (faltantes.length)
      e.password = `La contraseña no cumple: ${faltantes.map((r) => r.etiqueta.toLowerCase()).join(", ")}.`;
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
      const mensaje = await registrarse(form.nombre, form.correo, form.password);
      // RR_00_07: la cuenta nace sin verificar; se pide revisar el correo.
      navigate("/verify-email", { state: { correo: form.correo, mensaje } });
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo crear la cuenta.");
    } finally {
      setCargando(false);
    }
  };

  /** Props comunes de cada campo del formulario: valor, cambio y error. */
  const campo = (clave: keyof typeof form) => ({
    valor: form[clave],
    onCambiar: (valor: string) => setForm((f) => ({ ...f, [clave]: valor })),
    error: errores[clave],
  });

  return (
    <PantallaAcceso subtitulo="Crea tu cuenta para comenzar">
      <h2 className="text-lg font-semibold mb-6" style={{ color: "#1e3d2a" }}>
        Crear cuenta
      </h2>

      {errorGeneral && <Aviso tipo="error">{errorGeneral}</Aviso>}

      <form onSubmit={enviar} className="flex flex-col gap-4">
        <CampoTexto etiqueta="Nombre completo" autoComplete="name" marcador="Juan Pérez" {...campo("nombre")} />
        <CampoTexto etiqueta="Correo electrónico" tipo="email" autoComplete="email" marcador="tu@correo.com" {...campo("correo")} />
        <CampoTexto etiqueta="Contraseña" tipo="password" autoComplete="new-password" marcador="••••••••" {...campo("password")}>
          {form.password && <FuerzaContrasena password={form.password} />}
        </CampoTexto>
        <CampoTexto
          etiqueta="Confirmar contraseña"
          tipo="password"
          autoComplete="new-password"
          marcador="••••••••"
          {...campo("confirmar")}
        />

        <p className="text-xs" style={{ color: "#8aab92" }}>
          Al registrarte se te asignará el rol de{" "}
          <strong style={{ color: "#2d5a3d" }}>usuario estándar</strong>, con más consultas
          diarias que las disponibles sin cuenta.
        </p>

        <BotonPrincipal tipo="submit" deshabilitado={cargando}>
          {cargando ? "Creando cuenta..." : "Crear cuenta"}
        </BotonPrincipal>
      </form>

      <p className="text-center text-sm mt-5" style={{ color: "#6b8f74" }}>
        ¿Ya tienes cuenta?{" "}
        <Link to="/login" className="font-medium" style={{ color: "#2d5a3d" }}>
          Inicia sesión
        </Link>
      </p>
    </PantallaAcceso>
  );
}
