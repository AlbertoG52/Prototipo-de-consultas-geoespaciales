/**
 * Marco de la aplicación: barra lateral y contenido.
 *
 * Es la primera vista que ve cualquier usuario, con o sin cuenta.
 * (RR_00_11). La barra lateral cambia según el tipo de sesión: el visitante no
 * tiene historial ni perfil, y su contador de consultas es más bajo.
 */
import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";

import { LayoutGrid, LogOut, User } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useConsultas } from "../context/ConsultasContext";
import { Logo } from "../components/Logo";
import { NOMBRE_APP, SUBTITULO_APP } from "../config/marca";

/** Convierte una fecha ISO en algo corto: "hace 2 min", "ayer", "lun". */
function tiempoRelativo(iso: string): string {
  const fecha = new Date(iso);
  const minutos = Math.floor((Date.now() - fecha.getTime()) / 60000);
  if (minutos < 1) return "ahora";
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias === 1) return "ayer";
  if (dias < 7) return fecha.toLocaleDateString("es-CR", { weekday: "short" });
  return fecha.toLocaleDateString("es-CR", { day: "numeric", month: "short" });
}

export function Root() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sesion, autenticado, salir, sesionExpirada } = useAuth();
  const { conversaciones, conversacionActual, abrirConversacion, nuevaConsulta } = useConsultas();

  // RR_00_04 criterio 3: al expirar por inactividad se limpia la conversación
  // (puede tener datos de la cuenta) y se pide iniciar sesión de nuevo.
  useEffect(() => {
    if (!sesionExpirada) return;
    nuevaConsulta();
    navigate("/login", { replace: true });
  }, [sesionExpirada, nuevaConsulta, navigate]);

  const esAdmin = location.pathname === "/admin";
  const esPerfil = location.pathname === "/profile";

  const limite = sesion?.limite_consultas ?? 0;
  const restantes = sesion?.consultas_restantes ?? 0;
  const porcentaje = limite > 0 ? (restantes / limite) * 100 : 0;

  const irAlAgente = () => {
    nuevaConsulta();
    navigate("/");
  };

  const manejarSalida = async () => {
    await salir();
    nuevaConsulta();
    navigate("/");
  };

  return (
    <div
      className="flex h-full"
      style={{ background: "var(--color-fondo)", fontFamily: "'Inter', sans-serif" }}
    >
      <aside
        className="flex flex-col shrink-0 border-r"
        style={{ width: 260, background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}
      >
        {/*
          RR_01 — acceso al agente de IA.
        */}
        <button
          onClick={irAlAgente}
          aria-label="Abrir el agente de flora"
          className="flex items-center gap-3 px-5 py-5 w-full text-left"
          style={{ border: "none", background: "transparent", cursor: "pointer" }}
        >
          <Logo tamano={40} redondeo={12} />
          <div>
            <div className="font-semibold text-sm" style={{ color: "var(--color-texto)" }}>
              {NOMBRE_APP}
            </div>
            <div className="text-xs" style={{ color: "var(--color-texto-secundario)" }}>
              {SUBTITULO_APP}
            </div>
          </div>
        </button>

        <div className="px-4 mb-4">
          <button
            onClick={irAlAgente}
            className="w-full flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium transition-all"
            style={{ border: "1.5px solid var(--color-borde-marca)", color: "var(--color-texto-marca)", background: "transparent" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-superficie-marca)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
            Nueva consulta
          </button>
        </div>

        {/*
          RR_09 — historial por conversaciones, la de actividad más reciente
          primero. Se conserva aunque la persona cierre sesión y vuelva a entrar.
          Para un visitante sin cuenta la lista no existe: sus consultas no se
          guardan (RR_00_11.
        */}
        <div className="flex-1 overflow-y-auto px-3">
          <div className="text-xs font-medium mb-2 px-2" style={{ color: "var(--color-texto-secundario)" }}>
            Tu historial
          </div>

          {!sesion?.guarda_historial ? (
            <div
              className="text-xs leading-relaxed rounded-lg px-3 py-3 mx-1"
              style={{ background: "var(--color-fondo)", color: "var(--color-texto-tenue)", border: "1px dashed var(--color-borde)" }}
            >
              Estás consultando sin cuenta, así que tus consultas no se guardan.
              <button
                onClick={() => navigate("/login")}
                className="block mt-2 font-medium"
                style={{ color: "var(--color-texto-marca)", border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
              >
                Inicia sesión para conservarlas
              </button>
            </div>
          ) : conversaciones.length === 0 ? (
            <div className="text-xs px-3 py-2" style={{ color: "var(--color-texto-suave)" }}>
              Todavía no has consultado nada.
            </div>
          ) : (
            <div className="flex flex-col gap-0.5">
              {conversaciones.map((c) => {
                const abierta = c.id === conversacionActual;
                const fondo = abierta ? "var(--color-superficie-marca)" : "transparent";
                return (
                <button
                  key={c.id}
                  aria-current={abierta ? "true" : undefined}
                  onClick={() => {
                    // No repite las consultas: recupera la conversación guardada.
                    void abrirConversacion(c.id);
                    navigate("/");
                  }}
                  className="w-full text-left rounded-lg px-3 py-2.5 transition-all"
                  style={{ background: fondo, border: "none", cursor: "pointer" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = abierta ? fondo : "var(--color-superficie-hover)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = fondo;
                  }}
                >
                  <div
                    className="text-sm leading-snug line-clamp-2"
                    style={{ color: "var(--color-texto-cuerpo)" }}
                  >
                    {c.titulo}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>
                    {tiempoRelativo(c.actualizada_en)}
                  </div>
                </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Navegación inferior — depende de si hay cuenta detrás de la sesión. */}
        <div className="px-3 py-3 flex flex-col gap-1" style={{ borderTop: "1px solid var(--color-borde)" }}>
          {autenticado ? (
            <>
              <button
                onClick={() => navigate("/profile")}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all w-full text-left"
                style={{
                  background: esPerfil ? "var(--color-superficie-marca)" : "transparent",
                  color: "var(--color-texto-cuerpo)",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <User size={16} strokeWidth={1.8} style={{ color: "var(--color-texto-marca)" }} />
                Mi perfil
              </button>

              {sesion?.usuario?.rol === "supermoderador" && (
                <button
                  onClick={() => navigate("/admin")}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all w-full text-left"
                  style={{
                    background: esAdmin ? "var(--color-superficie-marca)" : "transparent",
                    color: "var(--color-texto-cuerpo)",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  <LayoutGrid size={16} strokeWidth={1.8} style={{ color: "var(--color-texto-marca)" }} />
                  Administración
                </button>
              )}

              {/* RR_00_01 cerrar la sesión activa. */}
              <button
                onClick={manejarSalida}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all w-full text-left"
                style={{ background: "transparent", color: "var(--color-texto-cuerpo)", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--color-superficie-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                }}
              >
                <LogOut size={16} strokeWidth={1.8} style={{ color: "var(--color-texto-marca)" }} />
                Cerrar sesión
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => navigate("/login")}
                className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all w-full"
                style={{ background: "var(--color-marca)", color: "var(--color-sobre-marca)", border: "none", cursor: "pointer" }}
              >
                Iniciar sesión
              </button>
              <button
                onClick={() => navigate("/register")}
                className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm transition-all w-full"
                style={{ background: "transparent", color: "var(--color-texto-marca)", border: "none", cursor: "pointer" }}
              >
                Crear cuenta
              </button>
            </>
          )}
        </div>

        {/*
          Consultas restantes.
          RR_00_11: sin cuenta el límite diario es menor.
        */}
        <div
          className="mx-3 mb-4 rounded-xl px-4 py-3"
          style={{ background: "var(--color-superficie-suave)", border: "1px solid var(--color-borde)" }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs" style={{ color: "var(--color-texto-cuerpo)" }}>
              Consultas restantes
            </span>
            <span className="text-xs font-semibold" style={{ color: "var(--color-texto)" }}>
              {sesion ? `${restantes}/${limite}` : "…"}
            </span>
          </div>
          <div className="rounded-full overflow-hidden" style={{ height: 5, background: "var(--color-borde-fuerte)" }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${porcentaje}%`,
                background: restantes === 0 ? "var(--color-error)" : "var(--color-marca)",
                transition: "width 0.3s",
              }}
            />
          </div>
          {!autenticado && (
            <div className="text-xs mt-2 leading-snug" style={{ color: "var(--color-texto-tenue)" }}>
              Con una cuenta tienes más consultas al día.
            </div>
          )}
        </div>
      </aside>

      <main className="flex flex-col flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
