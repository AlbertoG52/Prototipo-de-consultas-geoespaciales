/**
 * Perfil del usuario registrado.
 *
 * Pestañas:
 *  - Perfil: nombre (editable) y correo (solo lectura).
 *  - Preferencias: apariencia (modo oscuro y tipo de letra), guardada en el
 *    navegador. Al moderador y al supermoderador también le muestra si sus
 *    respuestas incluyen el mapa y las fuentes (RR_67, RR_68), guardado en su
 *    cuenta para que se conserve entre sesiones (RR_79).
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
import { ChevronDown } from "lucide-react";

import { Aviso, BotonPrincipal, CampoTexto } from "../components/Formulario";
import { FuerzaContrasena, cumpleReglasPassword } from "../components/FuerzaContrasena";
import { Interruptor } from "../components/Interruptor";
import { useAuth } from "../context/AuthContext";
import * as api from "../services/api";
import type { PreferenciasModerador } from "../types";
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
    <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
      <div className="flex items-center gap-2 mb-1">
        <h3 className="font-semibold" style={{ color: "var(--color-texto)" }}>
          {titulo}
        </h3>
        {etiqueta && (
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: "var(--color-superficie-suave)", color: "var(--color-texto-tenue)" }}
          >
            {etiqueta}
          </span>
        )}
      </div>
      {descripcion && (
        <p className="text-xs mb-4" style={{ color: "var(--color-texto-tenue)" }}>
          {descripcion}
        </p>
      )}
      {children}
    </div>
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
  const fuenteActual = FUENTES.find((f) => f.id === fuente) ?? FUENTES[0];

  // RR_67: la configuración de respuestas es solo del moderador y del supermoderador.
  const { sesion } = useAuth();
  const rol = sesion?.usuario?.rol;
  const configuraRespuestas = rol === "moderador" || rol === "supermoderador";

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
          <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "var(--color-superficie-suave)" }}>
            <div>
              <div className="text-sm font-medium" style={{ color: "var(--color-texto)" }}>
                Modo oscuro
              </div>
              <div className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
                Fondo oscuro y texto claro, más cómodo con poca luz.
              </div>
            </div>
            <Interruptor activo={tema === "oscuro"} onCambiar={cambiarTema} etiqueta="Modo oscuro" />
          </div>

          <div>
            <label htmlFor="fuente-app" className="block text-sm font-medium mb-2" style={{ color: "var(--color-texto)" }}>
              Tipo de letra
            </label>
            <div className="relative">
              {/* Cada opción se muestra con su propia letra (si el navegador lo permite). */}
              <select
                id="fuente-app"
                value={fuente}
                onChange={(e) => cambiarFuente(e.target.value as Fuente)}
                className="w-full appearance-none rounded-xl px-4 py-3 pr-10 text-sm cursor-pointer"
                style={{
                  background: "var(--color-fondo)",
                  border: "1.5px solid var(--color-borde-fuerte)",
                  color: "var(--color-texto)",
                  fontFamily: fuenteActual.css,
                }}
              >
                {FUENTES.map((f) => (
                  <option key={f.id} value={f.id} style={{ fontFamily: f.css }}>
                    {f.nombre}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={16}
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: "var(--color-texto-secundario)" }}
              />
            </div>
            <p className="text-xs mt-2" style={{ color: "var(--color-texto-tenue)", fontFamily: fuenteActual.css }}>
              {fuenteActual.descripcion}
            </p>
          </div>
        </div>
      </Tarjeta>

      {configuraRespuestas && <ConfiguracionDeRespuestas />}
    </div>
  );
}

/** Una opción de la configuración de respuestas, con su interruptor. */
function OpcionDeRespuesta({
  titulo,
  descripcion,
  activa,
  propia,
  porDefecto,
  deshabilitada,
  onCambiar,
  onRestablecer,
}: {
  titulo: string;
  descripcion: string;
  activa: boolean;
  propia: boolean;
  porDefecto: boolean;
  deshabilitada: boolean;
  onCambiar: () => void;
  onRestablecer: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 p-4 rounded-xl" style={{ background: "var(--color-superficie-suave)" }}>
      <div>
        <div className="text-sm font-medium" style={{ color: "var(--color-texto)" }}>
          {titulo}
        </div>
        <div className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
          {descripcion}
        </div>
        {/* RR_80: si no la ha cambiado, sigue la del sistema. */}
        <div className="text-xs mt-1" style={{ color: "var(--color-texto-tenue)" }}>
          {propia ? (
            <>
              Preferencia propia ·{" "}
              <button
                type="button"
                onClick={onRestablecer}
                disabled={deshabilitada}
                className="underline"
                style={{ background: "none", border: "none", padding: 0, color: "var(--color-texto-marca)", cursor: "pointer" }}
              >
                usar la del sistema ({porDefecto ? "incluir" : "no incluir"})
              </button>
            </>
          ) : (
            "Según la configuración del sistema"
          )}
        </div>
      </div>
      <Interruptor activo={activa} onCambiar={onCambiar} etiqueta={titulo} deshabilitado={deshabilitada} />
    </div>
  );
}

/**
 * RR_67, RR_68, RR_79 — si las respuestas del moderador incluyen el mapa y las
 * fuentes. Se guarda en la cuenta al instante y aplica desde la consulta
 * siguiente; mientras no la cambie, sigue la del sistema (RR_80).
 */
function ConfiguracionDeRespuestas() {
  const [preferencias, setPreferencias] = useState<PreferenciasModerador | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    api
      .obtenerPreferencias()
      .then((p) => {
        if (vigente) setPreferencias(p);
      })
      .catch((err) => {
        if (vigente) setError(err instanceof Error ? err.message : "No se pudo cargar la configuración.");
      });
    return () => {
      vigente = false;
    };
  }, []);

  async function cambiar(cambio: { incluir_mapa?: boolean | null; incluir_fuentes?: boolean | null }) {
    setGuardando(true);
    setError(null);
    try {
      setPreferencias(await api.cambiarPreferencias(cambio));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la configuración.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Tarjeta
      titulo="Configuración de respuestas"
      descripcion="Personaliza cómo el agente presenta los resultados de tus consultas. Se guarda en tu cuenta y aplica desde tu siguiente consulta."
    >
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!preferencias ? (
        !error && (
          <p className="text-sm" style={{ color: "var(--color-texto-tenue)" }}>
            Cargando…
          </p>
        )
      ) : (
        <div className="flex flex-col gap-4">
          <OpcionDeRespuesta
            titulo="Incluir mapa de distribución"
            descripcion="Muestra el mapa geoespacial junto a la respuesta cuando hay datos disponibles."
            activa={preferencias.incluir_mapa}
            propia={preferencias.mapa_propio}
            porDefecto={preferencias.por_defecto.incluir_mapa}
            deshabilitada={guardando}
            onCambiar={() => void cambiar({ incluir_mapa: !preferencias.incluir_mapa })}
            onRestablecer={() => void cambiar({ incluir_mapa: null })}
          />
          <OpcionDeRespuesta
            titulo="Mostrar fuentes de información"
            descripcion="Lista las fuentes utilizadas (GBIF, Manual de Plantas de CR) y las citas dentro de cada respuesta."
            activa={preferencias.incluir_fuentes}
            propia={preferencias.fuentes_propio}
            porDefecto={preferencias.por_defecto.incluir_fuentes}
            deshabilitada={guardando}
            onCambiar={() => void cambiar({ incluir_fuentes: !preferencias.incluir_fuentes })}
            onRestablecer={() => void cambiar({ incluir_fuentes: null })}
          />
        </div>
      )}
    </Tarjeta>
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
                  background: elegida ? "var(--color-superficie-marca)" : "var(--color-superficie-suave)",
                  border: `1.5px solid ${elegida ? "var(--color-borde-marca)" : "transparent"}`,
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
                  style={{ accentColor: "var(--color-marca)" }}
                />
                <span
                  className="text-sm"
                  style={{ color: elegida ? "var(--color-texto)" : "var(--color-texto-cuerpo)", fontWeight: elegida ? 500 : 400 }}
                >
                  {opt.label}
                </span>
                {opt.minutos === 30 && (
                  <span className="text-xs ml-auto" style={{ color: "var(--color-texto-tenue)" }}>
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
      <div className="px-4 md:px-8 py-4 md:py-5 border-b shrink-0" style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}>
        <h1 className="text-xl font-semibold" style={{ color: "var(--color-texto)" }}>
          Mi perfil
        </h1>
        <p className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>
          Gestiona tu cuenta y tus preferencias
        </p>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ background: "var(--color-fondo)" }}>
        <div className="px-4 md:px-8 py-6 md:py-8" style={{ background: "var(--color-superficie)", borderBottom: "1px solid var(--color-borde)" }}>
          <div className="flex items-center gap-5 max-w-2xl">
            <div
              className="flex items-center justify-center rounded-full text-2xl font-bold"
              style={{ width: 72, height: 72, background: "var(--color-marca)", color: "var(--color-sobre-marca)", flexShrink: 0 }}
              aria-hidden="true"
            >
              {iniciales(usuario.nombre, usuario.correo)}
            </div>
            <div className="min-w-0">
              <h2
                className="text-xl font-bold truncate"
                style={{ color: "var(--color-texto)", fontFamily: "var(--font-serif)" }}
              >
                {usuario.nombre || "Sin nombre"}
              </h2>
              <p className="text-sm truncate" style={{ color: "var(--color-texto-secundario)" }}>
                {usuario.correo}
              </p>
            </div>
          </div>
        </div>

        <div className="border-b px-4 md:px-8 overflow-x-auto" style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}>
          <div className="flex gap-0 max-w-2xl" role="tablist">
            {PESTANAS.map((t) => {
              const activa = pestana === t.id;
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={activa}
                  onClick={() => setPestana(t.id)}
                  className="px-4 md:px-5 py-3.5 text-sm font-medium transition-all whitespace-nowrap"
                  style={{
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    borderBottom: activa ? "2px solid var(--color-borde-marca)" : "2px solid transparent",
                    color: activa ? "var(--color-texto-marca)" : "var(--color-texto-tenue)",
                    marginBottom: -1,
                  }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-4 md:px-8 py-6 max-w-2xl">
          {pestana === "perfil" && <PestanaPerfil />}
          {pestana === "preferencias" && <PestanaPreferencias />}
          {pestana === "seguridad" && <PestanaSeguridad />}
        </div>
      </div>
    </>
  );
}
