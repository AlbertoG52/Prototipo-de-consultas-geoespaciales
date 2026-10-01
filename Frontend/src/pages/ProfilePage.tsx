/**
 * Perfil del usuario registrado.
 *
 * Pestañas:
 *  - Perfil: nombre (editable) y correo (solo lectura).
 *  - Preferencias: apariencia (modo oscuro y tipo de letra), guardada en el
 *    navegador. La configuración de respuestas (RR_67 / RR_68) sigue siendo
 *    solo interfaz: la implementa otro requerimiento.
 *  - Seguridad: cambio de contraseña, validado en el servidor con las mismas
 *    reglas del registro (RR_00_03), y tiempo de inactividad que cierra la
 *    sesión (RR_00_04), guardado en la cuenta.
 *
 * No tiene pestaña de historial: el historial ya está en la barra lateral
 * (RR_09).
 *
 * Un visitante sin cuenta no tiene perfil: se le devuelve al agente.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router";

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { FuerzaContrasena, cumpleReglasPassword } from "../components/FuerzaContrasena";
import { useAuth } from "../context/AuthContext";
import * as api from "../services/api";
import {
  FUENTES,
  aplicarFuente,
  aplicarTema,
  leerFuente,
  leerTema,
  type Fuente,
  type Tema,
} from "../utils/apariencia";

type Pestana = "perfil" | "preferencias" | "seguridad";

const PESTANAS: { id: Pestana; label: string }[] = [
  { id: "perfil", label: "Perfil" },
  { id: "preferencias", label: "Preferencias" },
  { id: "seguridad", label: "Seguridad" },
];

// RR_00_04 — mismas opciones que acepta el servidor (config.OPCIONES_INACTIVIDAD).
// 0 = la sesión no se cierra por inactividad.
const OPCIONES_INACTIVIDAD: { label: string; minutos: number }[] = [
  { label: "30 minutos", minutos: 30 },
  { label: "1 hora", minutos: 60 },
  { label: "6 horas", minutos: 360 },
  { label: "12 horas", minutos: 720 },
  { label: "24 horas", minutos: 1440 },
  { label: "1 semana", minutos: 10080 },
  { label: "Nunca", minutos: 0 },
];

function iniciales(nombre: string | null, correo: string): string {
  const base = (nombre ?? "").trim() || correo;
  const partes = base.split(/\s+/).filter(Boolean);
  const letras = partes.length > 1 ? partes[0][0] + partes[1][0] : base.slice(0, 2);
  return letras.toUpperCase();
}

// ─── Piezas de interfaz ───

function Tarjeta({
  titulo,
  descripcion,
  etiqueta,
  children,
}: {
  titulo: string;
  descripcion?: string;
  etiqueta?: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
      <div className="flex items-center gap-2 mb-1">
        <h3 className="font-semibold" style={{ color: "#1e3d2a" }}>
          {titulo}
        </h3>
        {etiqueta && (
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: "#f0f5f1", color: "#8aab92" }}
          >
            {etiqueta}
          </span>
        )}
      </div>
      {descripcion && (
        <p className="text-xs mb-4" style={{ color: "#8aab92" }}>
          {descripcion}
        </p>
      )}
      {children}
    </div>
  );
}

function Interruptor({
  activo,
  onCambiar,
  etiqueta,
  deshabilitado = false,
}: {
  activo: boolean;
  onCambiar: () => void;
  etiqueta: string;
  deshabilitado?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      onClick={onCambiar}
      disabled={deshabilitado}
      className="relative rounded-full transition-all"
      style={{
        width: 44,
        height: 24,
        background: activo ? "#2d5a3d" : "#c5dccb",
        border: "none",
        cursor: deshabilitado ? "not-allowed" : "pointer",
        opacity: deshabilitado ? 0.6 : 1,
        flexShrink: 0,
      }}
    >
      <span
        className="absolute rounded-full transition-all"
        style={{
          width: 18,
          height: 18,
          background: "#fff",
          top: 3,
          left: activo ? 23 : 3,
          boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
        }}
      />
    </button>
  );
}

// ─── Pestañas ───

function PestanaPerfil() {
  const { sesion, refrescarSesion } = useAuth();
  const usuario = sesion!.usuario!;

  const [nombre, setNombre] = useState(usuario.nombre ?? "");
  const [guardando, setGuardando] = useState(false);
  const [exito, setExito] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Si la sesión se actualiza (por ejemplo, tras guardar), se refleja aquí.
  useEffect(() => setNombre(usuario.nombre ?? ""), [usuario.nombre]);

  const limpio = nombre.trim().replace(/\s+/g, " ");
  const sinCambios = limpio === (usuario.nombre ?? "");
  const invalido = limpio.length < 2;

  async function guardar() {
    setGuardando(true);
    setExito(false);
    setError(null);
    try {
      await api.cambiarNombre(limpio);
      await refrescarSesion();
      setExito(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el nombre.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Tarjeta titulo="Información personal">
      <div className="mt-3" />
      {exito && <Aviso tipo="exito">Cambios guardados correctamente.</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (!sinCambios && !invalido && !guardando) void guardar();
        }}
      >
        <CampoTexto
          etiqueta="Nombre"
          valor={nombre}
          autoComplete="name"
          onCambiar={(v) => {
            setNombre(v);
            setExito(false);
          }}
          ayuda={invalido ? "El nombre debe tener al menos 2 caracteres." : undefined}
        />
        <CampoTexto
          etiqueta="Correo electrónico"
          tipo="email"
          valor={usuario.correo}
          deshabilitado
          ayuda="El correo electrónico no se puede cambiar."
        />
        <BotonPrincipal bloque={false} tipo="submit" deshabilitado={sinCambios || invalido || guardando}>
          {guardando ? "Guardando…" : "Guardar cambios"}
        </BotonPrincipal>
      </form>
    </Tarjeta>
  );
}

function PestanaPreferencias() {
  const [tema, setTema] = useState<Tema>(leerTema);
  const [fuente, setFuente] = useState<Fuente>(leerFuente);

  // RR_67 / RR_68: solo interfaz por ahora; no se guardan ni afectan las respuestas.
  const [incluirMapa, setIncluirMapa] = useState(true);
  const [incluirFuentes, setIncluirFuentes] = useState(true);

  function cambiarTema() {
    const nuevo: Tema = tema === "oscuro" ? "claro" : "oscuro";
    aplicarTema(nuevo);
    setTema(nuevo);
  }

  function cambiarFuente(nueva: Fuente) {
    aplicarFuente(nueva);
    setFuente(nueva);
  }

  return (
    <div className="flex flex-col gap-4">
      <Tarjeta
        titulo="Apariencia"
        descripcion="Los cambios se aplican al instante y se recuerdan en este navegador."
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "#f0f5f1" }}>
            <div>
              <div className="text-sm font-medium" style={{ color: "#1e3d2a" }}>
                Modo oscuro
              </div>
              <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>
                Fondo oscuro y texto claro, más cómodo con poca luz.
              </div>
            </div>
            <Interruptor activo={tema === "oscuro"} onCambiar={cambiarTema} etiqueta="Modo oscuro" />
          </div>

          <fieldset>
            <legend className="text-sm font-medium mb-2" style={{ color: "#1e3d2a" }}>
              Tipo de letra
            </legend>
            <div className="flex flex-col gap-2">
              {FUENTES.map((f) => {
                const elegida = fuente === f.id;
                return (
                  <label
                    key={f.id}
                    className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
                    style={{
                      background: elegida ? "#e8f0eb" : "#f0f5f1",
                      border: `1.5px solid ${elegida ? "#2d5a3d" : "transparent"}`,
                    }}
                  >
                    <input
                      type="radio"
                      name="fuente"
                      value={f.id}
                      checked={elegida}
                      onChange={() => cambiarFuente(f.id)}
                      style={{ accentColor: "#2d5a3d" }}
                    />
                    <span className="flex-1">
                      {/* Cada opción se muestra con su propia letra. */}
                      <span className="block text-sm" style={{ color: "#1e3d2a", fontFamily: f.css }}>
                        {f.nombre}
                      </span>
                      <span className="block text-xs" style={{ color: "#8aab92", fontFamily: f.css }}>
                        {f.descripcion}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        </div>
      </Tarjeta>

      <Tarjeta
        titulo="Configuración de respuestas"
        etiqueta="Próximamente"
        descripcion="Personaliza cómo el agente presenta los resultados de tus consultas."
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "#f0f5f1" }}>
            <div>
              <div className="text-sm font-medium" style={{ color: "#1e3d2a" }}>
                Incluir mapa de distribución
              </div>
              <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>
                Muestra el mapa geoespacial junto a la respuesta cuando hay datos disponibles.
              </div>
            </div>
            <Interruptor
              activo={incluirMapa}
              onCambiar={() => setIncluirMapa((v) => !v)}
              etiqueta="Incluir mapa de distribución"
            />
          </div>
          <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "#f0f5f1" }}>
            <div>
              <div className="text-sm font-medium" style={{ color: "#1e3d2a" }}>
                Mostrar fuentes de información
              </div>
              <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>
                Lista las fuentes utilizadas (GBIF, Manual de Plantas de CR) al final de cada respuesta.
              </div>
            </div>
            <Interruptor
              activo={incluirFuentes}
              onCambiar={() => setIncluirFuentes((v) => !v)}
              etiqueta="Mostrar fuentes de información"
            />
          </div>
        </div>
      </Tarjeta>
    </div>
  );
}

function PestanaSeguridad() {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [exito, setExito] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // RR_00_04 criterio 2: el periodo de inactividad es configurable por cuenta.
  const { sesion, refrescarSesion } = useAuth();
  const inactividad = sesion?.minutos_inactividad ?? null;
  const [guardandoInactividad, setGuardandoInactividad] = useState(false);
  const [errorInactividad, setErrorInactividad] = useState<string | null>(null);

  async function elegirInactividad(minutos: number) {
    if (minutos === inactividad || guardandoInactividad) return;
    setGuardandoInactividad(true);
    setErrorInactividad(null);
    try {
      await api.cambiarInactividad(minutos);
      await refrescarSesion();
    } catch (err) {
      setErrorInactividad(
        err instanceof Error ? err.message : "No se pudo guardar el tiempo de inactividad.",
      );
    } finally {
      setGuardandoInactividad(false);
    }
  }

  const cumpleReglas = cumpleReglasPassword(nueva);
  const coinciden = nueva.length > 0 && nueva === confirmacion;
  const listo = actual.length > 0 && cumpleReglas && coinciden && !guardando;

  async function guardar() {
    setGuardando(true);
    setExito(false);
    setError(null);
    try {
      await api.cambiarPassword(actual, nueva);
      setActual("");
      setNueva("");
      setConfirmacion("");
      setExito(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Tarjeta titulo="Cambiar contraseña" descripcion="Por seguridad, primero confirma tu contraseña actual.">
        {exito && <Aviso tipo="exito">Tu contraseña se cambió correctamente.</Aviso>}
        {error && <Aviso tipo="error">{error}</Aviso>}
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (listo) void guardar();
          }}
        >
          <CampoTexto
            etiqueta="Contraseña actual"
            tipo="password"
            valor={actual}
            autoComplete="current-password"
            onCambiar={(v) => {
              setActual(v);
              setExito(false);
            }}
          />
          <CampoTexto
            etiqueta="Nueva contraseña"
            tipo="password"
            valor={nueva}
            autoComplete="new-password"
            onCambiar={(v) => {
              setNueva(v);
              setExito(false);
            }}
          />
          <div className="-mt-3">
            <FuerzaContrasena password={nueva} />
          </div>
          <CampoTexto
            etiqueta="Confirmar nueva contraseña"
            tipo="password"
            valor={confirmacion}
            autoComplete="new-password"
            onCambiar={(v) => {
              setConfirmacion(v);
              setExito(false);
            }}
            ayuda={confirmacion && !coinciden ? "Las contraseñas no coinciden." : undefined}
          />
          <div className="mt-1">
            <BotonPrincipal bloque={false} tipo="submit" deshabilitado={!listo}>
              {guardando ? "Actualizando…" : "Actualizar contraseña"}
            </BotonPrincipal>
          </div>
        </form>
      </Tarjeta>

      <Tarjeta
        titulo="Tiempo de inactividad"
        descripcion="Elige cuánto tiempo debe pasar sin actividad para cerrar la sesión automáticamente."
      >
        {errorInactividad && <Aviso tipo="error">{errorInactividad}</Aviso>}
        <div className="flex flex-col gap-2" role="radiogroup" aria-label="Tiempo de inactividad">
          {OPCIONES_INACTIVIDAD.map((opt) => {
            const elegida = inactividad === opt.minutos;
            return (
              <label
                key={opt.minutos}
                className="flex items-center gap-3 p-3 rounded-xl transition-all"
                style={{
                  background: elegida ? "#e8f0eb" : "#f0f5f1",
                  border: `1.5px solid ${elegida ? "#2d5a3d" : "transparent"}`,
                  cursor: guardandoInactividad ? "default" : "pointer",
                  opacity: guardandoInactividad && !elegida ? 0.6 : 1,
                }}
              >
                <input
                  type="radio"
                  name="inactividad"
                  value={opt.minutos}
                  checked={elegida}
                  disabled={guardandoInactividad}
                  onChange={() => void elegirInactividad(opt.minutos)}
                  style={{ accentColor: "#2d5a3d" }}
                />
                <span
                  className="text-sm"
                  style={{ color: elegida ? "#1e3d2a" : "#374a3c", fontWeight: elegida ? 500 : 400 }}
                >
                  {opt.label}
                </span>
                {opt.minutos === 30 && (
                  <span className="text-xs ml-auto" style={{ color: "#8aab92" }}>
                    Recomendado
                  </span>
                )}
              </label>
            );
          })}
        </div>
      </Tarjeta>
    </div>
  );
}

// ─── Página ───

export function ProfilePage() {
  const { sesion, cargando, autenticado } = useAuth();
  const [pestana, setPestana] = useState<Pestana>("perfil");

  if (cargando || !sesion) return null;
  if (!autenticado || !sesion.usuario) return <Navigate to="/" replace />;

  const usuario = sesion.usuario;

  return (
    <>
      <div className="px-8 py-5 border-b shrink-0" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        <h1 className="text-xl font-semibold" style={{ color: "#1e3d2a" }}>
          Mi perfil
        </h1>
        <p className="text-sm" style={{ color: "#6b8f74" }}>
          Gestiona tu cuenta y tus preferencias
        </p>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ background: "#f7f8f5" }}>
        <div className="px-8 py-8" style={{ background: "#ffffff", borderBottom: "1px solid #dde8df" }}>
          <div className="flex items-center gap-5 max-w-2xl">
            <div
              className="flex items-center justify-center rounded-full text-2xl font-bold"
              style={{ width: 72, height: 72, background: "#2d5a3d", color: "#fff", flexShrink: 0 }}
              aria-hidden="true"
            >
              {iniciales(usuario.nombre, usuario.correo)}
            </div>
            <div className="min-w-0">
              <h2
                className="text-xl font-bold truncate"
                style={{ color: "#1e3d2a", fontFamily: "'Lora', serif" }}
              >
                {usuario.nombre || "Sin nombre"}
              </h2>
              <p className="text-sm truncate" style={{ color: "#6b8f74" }}>
                {usuario.correo}
              </p>
            </div>
          </div>
        </div>

        <div className="border-b px-8" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
          <div className="flex gap-0 max-w-2xl" role="tablist">
            {PESTANAS.map((t) => {
              const activa = pestana === t.id;
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={activa}
                  onClick={() => setPestana(t.id)}
                  className="px-5 py-3.5 text-sm font-medium transition-all"
                  style={{
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    borderBottom: activa ? "2px solid #2d5a3d" : "2px solid transparent",
                    color: activa ? "#2d5a3d" : "#8aab92",
                    marginBottom: -1,
                  }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-8 py-6 max-w-2xl">
          {pestana === "perfil" && <PestanaPerfil />}
          {pestana === "preferencias" && <PestanaPreferencias />}
          {pestana === "seguridad" && <PestanaSeguridad />}
        </div>
      </div>
    </>
  );
}
