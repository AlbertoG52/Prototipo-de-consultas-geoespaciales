/**
 * Marco de la aplicación: barra lateral y contenido.
 *
 * Es la primera vista que ve cualquier usuario, con o sin cuenta.
 * (RR_00_11). La barra lateral cambia según el tipo de sesión: el visitante no
 * tiene historial ni perfil, y su contador de consultas es más bajo.
 */
import { Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "../context/AuthContext";
import { useConsultas } from "../context/ConsultasContext";

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
  const { sesion, autenticado, salir } = useAuth();
  const { historial, verDelHistorial, nuevaConsulta } = useConsultas();

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
      style={{ background: "#f7f8f5", fontFamily: "'Inter', sans-serif" }}
    >
      <aside
        className="flex flex-col shrink-0 border-r"
        style={{ width: 260, background: "#ffffff", borderColor: "#dde8df" }}
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
          <div
            className="flex items-center justify-center rounded-xl shrink-0"
            style={{ width: 40, height: 40, background: "#2d5a3d" }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M6.5 20C4 20 2 17 2 14C2 9 6 5 11 4C16 3 21 5 21 10C21 16 17 20 12 20C10.5 20 9 19.5 8 18.5"
                stroke="white"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M12 20C12 20 8 16 8 12C8 8 11 5 12 4"
                stroke="white"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <div className="font-semibold text-sm" style={{ color: "#1e3d2a" }}>
              FloraBot CR
            </div>
            <div className="text-xs" style={{ color: "#6b8f74" }}>
              Agente de Flora
            </div>
          </div>
        </button>

        <div className="px-4 mb-4">
          <button
            onClick={irAlAgente}
            className="w-full flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium transition-all"
            style={{ border: "1.5px solid #2d5a3d", color: "#2d5a3d", background: "transparent" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#e8f0eb";
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
          RR_09 — historial de la sesión activa, en orden cronológico.
          Para un visitante sin cuenta la lista no existe: sus consultas no se
          guardan (RR_00_11.
        */}
        <div className="flex-1 overflow-y-auto px-3">
          <div className="text-xs font-medium mb-2 px-2" style={{ color: "#6b8f74" }}>
            Consultas de esta sesión
          </div>

          {!sesion?.guarda_historial ? (
            <div
              className="text-xs leading-relaxed rounded-lg px-3 py-3 mx-1"
              style={{ background: "#f7f8f5", color: "#8aab92", border: "1px dashed #dde8df" }}
            >
              Estás consultando sin cuenta, así que tus consultas no se guardan.
              <button
                onClick={() => navigate("/login")}
                className="block mt-2 font-medium"
                style={{ color: "#2d5a3d", border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
              >
                Inicia sesión para conservarlas
              </button>
            </div>
          ) : historial.length === 0 ? (
            <div className="text-xs px-3 py-2" style={{ color: "#a8d4b0" }}>
              Todavía no has consultado nada.
            </div>
          ) : (
            <div className="flex flex-col gap-0.5">
              {historial.map((h) => (
                <button
                  key={h.id}
                  onClick={() => {
                    // No repite la consulta: recupera la respuesta guardada.
                    verDelHistorial(h.id);
                    navigate("/");
                  }}
                  className="w-full text-left rounded-lg px-3 py-2.5 transition-all"
                  style={{ background: "transparent", border: "none", cursor: "pointer" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "#f2f6f3";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <div
                    className="text-sm leading-snug line-clamp-2"
                    style={{ color: "#374a3c" }}
                  >
                    {h.texto}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>
                    {tiempoRelativo(h.realizada_en)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Navegación inferior — depende de si hay cuenta detrás de la sesión. */}
        <div className="px-3 py-3 flex flex-col gap-1" style={{ borderTop: "1px solid #dde8df" }}>
          {autenticado ? (
            <>
              <button
                onClick={() => navigate("/profile")}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all w-full text-left"
                style={{
                  background: esPerfil ? "#e8f0eb" : "transparent",
                  color: "#374a3c",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="8" r="4" stroke="#2d5a3d" strokeWidth="1.8" />
                  <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="#2d5a3d" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
                Mi perfil
              </button>

              {sesion?.usuario?.rol === "supermoderador" && (
                <button
                  onClick={() => navigate("/admin")}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all w-full text-left"
                  style={{
                    background: esAdmin ? "#e8f0eb" : "transparent",
                    color: "#374a3c",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="#2d5a3d" strokeWidth="1.8" />
                    <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="#2d5a3d" strokeWidth="1.8" />
                    <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="#2d5a3d" strokeWidth="1.8" />
                    <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="#2d5a3d" strokeWidth="1.8" />
                  </svg>
                  Administración
                </button>
              )}

              {/* RR_00_01 cerrar la sesión activa. */}
              <button
                onClick={manejarSalida}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all w-full text-left"
                style={{ background: "transparent", color: "#374a3c", border: "none", cursor: "pointer" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#f2f6f3";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"
                    stroke="#2d5a3d"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Cerrar sesión
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => navigate("/login")}
                className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all w-full"
                style={{ background: "#2d5a3d", color: "#ffffff", border: "none", cursor: "pointer" }}
              >
                Iniciar sesión
              </button>
              <button
                onClick={() => navigate("/register")}
                className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm transition-all w-full"
                style={{ background: "transparent", color: "#2d5a3d", border: "none", cursor: "pointer" }}
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
          style={{ background: "#f0f5f1", border: "1px solid #dde8df" }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs" style={{ color: "#3d6040" }}>
              Consultas restantes
            </span>
            <span className="text-xs font-semibold" style={{ color: "#1e3d2a" }}>
              {restantes}/{limite}
            </span>
          </div>
          <div className="rounded-full overflow-hidden" style={{ height: 5, background: "#c5dccb" }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${porcentaje}%`,
                background: restantes === 0 ? "#dc2626" : "#2d5a3d",
                transition: "width 0.3s",
              }}
            />
          </div>
          {!autenticado && (
            <div className="text-xs mt-2 leading-snug" style={{ color: "#8aab92" }}>
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
