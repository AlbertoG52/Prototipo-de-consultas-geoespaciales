/**
 * Marco de la aplicación: barra lateral y contenido.
 *
 * Es la primera vista que ve cualquier usuario, con o sin cuenta.
 * (RR_00_11). La barra lateral cambia según el tipo de sesión: el visitante no
 * tiene historial ni perfil, y su contador de consultas es más bajo.
 *
 * Diseño adaptable:
 *  - Pantallas chicas (< md): la barra lateral se oculta y se abre como panel
 *    encima del contenido con el botón de menú de la barra superior.
 *  - Pantallas grandes: la barra lateral está fija y se puede plegar; la
 *    preferencia se recuerda en el navegador.
 *  - El pie de la barra lateral (perfil y consultas restantes) y el área donde
 *    se escribe la consulta (ChatPage) se alinean: cada uno publica su altura
 *    natural (--alto-pie-lateral y --alto-pie-chat, en <html>) y los dos usan
 *    la mayor como altura mínima, así su línea divisoria queda a la misma altura.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";

import { ChevronsUpDown, LayoutGrid, LogOut, Menu, PanelLeftClose, User, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useConsultas } from "../context/ConsultasContext";
import { Logo } from "../components/Logo";
import { NOMBRE_APP, SUBTITULO_APP } from "../config/marca";
import { IDIOMA_FECHAS } from "../config/textos";

// Ancho desde el que la barra lateral deja de ser un panel flotante (md de Tailwind).
const CONSULTA_PANTALLA_GRANDE = "(min-width: 768px)";
const CLAVE_BARRA_PLEGADA = "barra-lateral-plegada";

function leerPlegada(): boolean {
  try {
    return localStorage.getItem(CLAVE_BARRA_PLEGADA) === "1";
  } catch {
    return false;
  }
}

function guardarPlegada(plegada: boolean) {
  try {
    localStorage.setItem(CLAVE_BARRA_PLEGADA, plegada ? "1" : "0");
  } catch {
    // Sin almacenamiento (p. ej. navegación privada): solo no se recuerda.
  }
}

function iniciales(nombre: string | null, correo: string): string {
  const base = (nombre ?? "").trim() || correo;
  const partes = base.split(/\s+/).filter(Boolean);
  const letras = partes.length > 1 ? partes[0][0] + partes[1][0] : base.slice(0, 2);
  return letras.toUpperCase();
}

/**
 * Consultas restantes del día (RR_00_11: sin cuenta el límite es menor).
 * En rojo cuando ya no quedan.
 */
function ContadorConsultas({
  restantes,
  limite,
  cargando = false,
  conBarra = false,
}: {
  restantes: number;
  limite: number;
  cargando?: boolean;
  conBarra?: boolean;
}) {
  const agotadas = !cargando && restantes === 0;
  const porcentaje = limite > 0 ? (restantes / limite) * 100 : 0;
  return (
    <span className="block">
      <span
        className="block text-xs truncate"
        title="Consultas restantes hoy"
        style={{ color: agotadas ? "var(--color-error)" : "var(--color-texto-secundario)" }}
      >
        {cargando ? "Consultas restantes: …" : `${conBarra ? "Quedan " : ""}${restantes}/${limite} consultas hoy`}
      </span>
      {conBarra && (
        <span className="block rounded-full overflow-hidden mt-1.5" style={{ height: 3, background: "var(--color-borde-fuerte)" }}>
          <span
            className="block h-full rounded-full"
            style={{
              width: `${porcentaje}%`,
              background: agotadas ? "var(--color-error)" : "var(--color-marca)",
              transition: "width 0.3s",
            }}
          />
        </span>
      )}
    </span>
  );
}

/** Una opción del menú de la cuenta. */
function OpcionDeMenu({
  icono: Icono,
  activa = false,
  onClick,
  children,
}: {
  icono: typeof User;
  activa?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm w-full text-left transition-all"
      style={{
        background: activa ? "var(--color-superficie-marca)" : "transparent",
        color: "var(--color-texto-cuerpo)",
        border: "none",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        if (!activa) e.currentTarget.style.background = "var(--color-superficie-hover)";
      }}
      onMouseLeave={(e) => {
        if (!activa) e.currentTarget.style.background = "transparent";
      }}
    >
      <Icono size={16} strokeWidth={1.8} style={{ color: "var(--color-texto-marca)" }} />
      {children}
    </button>
  );
}

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
  if (dias < 7) return fecha.toLocaleDateString(IDIOMA_FECHAS, { weekday: "short" });
  return fecha.toLocaleDateString(IDIOMA_FECHAS, { day: "numeric", month: "short" });
}

export function Root() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sesion, autenticado, salir, sesionExpirada } = useAuth();
  const { conversaciones, conversacionActual, abrirConversacion, nuevaConsulta } = useConsultas();

  // Pantallas chicas: panel abierto o cerrado. Pantallas grandes: barra plegada o no.
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [plegada, setPlegada] = useState(leerPlegada);
  const pieRef = useRef<HTMLDivElement>(null);
  const [menuCuentaAbierto, setMenuCuentaAbierto] = useState(false);
  const menuCuentaRef = useRef<HTMLDivElement>(null);

  const cerrarMenu = useCallback(() => setMenuAbierto(false), []);

  const cambiarPlegada = (valor: boolean) => {
    setPlegada(valor);
    guardarPlegada(valor);
  };

  const mostrarBarra = () => {
    if (window.matchMedia(CONSULTA_PANTALLA_GRANDE).matches) cambiarPlegada(false);
    else setMenuAbierto(true);
  };

  // Al cambiar de página se cierran el panel y el menú de la cuenta.
  useEffect(() => {
    cerrarMenu();
    setMenuCuentaAbierto(false);
  }, [location.pathname, cerrarMenu]);

  // Escape cierra el menú de la cuenta y, si no estaba abierto, el panel.
  useEffect(() => {
    if (!menuAbierto && !menuCuentaAbierto) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (menuCuentaAbierto) setMenuCuentaAbierto(false);
      else cerrarMenu();
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [menuAbierto, menuCuentaAbierto, cerrarMenu]);

  // Un clic fuera del menú de la cuenta lo cierra.
  useEffect(() => {
    if (!menuCuentaAbierto) return;
    const alTocar = (e: PointerEvent) => {
      if (!menuCuentaRef.current?.contains(e.target as Node)) setMenuCuentaAbierto(false);
    };
    document.addEventListener("pointerdown", alTocar);
    return () => document.removeEventListener("pointerdown", alTocar);
  }, [menuCuentaAbierto]);

  // Altura natural del pie (+1 px del borde) -> --alto-pie-lateral (ver el comentario del módulo).
  useEffect(() => {
    const pie = pieRef.current;
    if (!pie) return;
    const raiz = document.documentElement.style;
    const medir = () => raiz.setProperty("--alto-pie-lateral", `${pie.offsetHeight ? pie.offsetHeight + 1 : 0}px`);
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(pie);
    return () => {
      observador.disconnect();
      raiz.removeProperty("--alto-pie-lateral");
    };
  }, []);

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

  const irA = (ruta: string) => {
    setMenuCuentaAbierto(false);
    navigate(ruta);
  };

  const irAlAgente = () => {
    nuevaConsulta();
    navigate("/");
    cerrarMenu();
  };

  const manejarSalida = async () => {
    setMenuCuentaAbierto(false);
    await salir();
    nuevaConsulta();
    navigate("/");
    cerrarMenu();
  };

  return (
    <div
      className="flex h-full"
      style={{ background: "var(--color-fondo)", fontFamily: "var(--fuente-app)" }}
    >
      {/* Fondo oscuro detrás del panel en pantallas chicas; al tocarlo se cierra. */}
      {menuAbierto && (
        <div
          className="fixed inset-0 z-30 md:hidden"
          style={{ background: "rgba(0, 0, 0, 0.5)" }}
          onClick={cerrarMenu}
          aria-hidden="true"
        />
      )}

      <aside
        id="barra-lateral"
        className={`fixed inset-y-0 left-0 z-40 flex flex-col shrink-0 border-r transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${
          menuAbierto ? "translate-x-0" : "-translate-x-full max-md:invisible"
        } ${plegada ? "md:hidden" : ""}`}
        style={{ width: 260, maxWidth: "85vw", background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}
      >
        <div className="flex items-center">
          {/*
            RR_01 — acceso al agente de IA.
          */}
          <button
            onClick={irAlAgente}
            aria-label="Abrir el agente de flora"
            className="flex items-center gap-3 px-5 py-5 flex-1 min-w-0 text-left"
            style={{ border: "none", background: "transparent", cursor: "pointer" }}
          >
            <Logo tamano={40} redondeo={12} />
            <div className="min-w-0">
              <div className="font-semibold text-sm truncate" style={{ color: "var(--color-texto)" }}>
                {NOMBRE_APP}
              </div>
              <div className="text-xs truncate" style={{ color: "var(--color-texto-secundario)" }}>
                {SUBTITULO_APP}
              </div>
            </div>
          </button>
          {/* Pantallas chicas: cerrar el panel. Pantallas grandes: plegar la barra. */}
          <button
            onClick={cerrarMenu}
            aria-label="Cerrar el menú"
            className="md:hidden mr-3 p-2 rounded-lg"
            style={{ border: "none", background: "transparent", color: "var(--color-texto-secundario)", cursor: "pointer" }}
          >
            <X size={18} />
          </button>
          <button
            onClick={() => cambiarPlegada(true)}
            aria-label="Ocultar la barra lateral"
            title="Ocultar la barra lateral"
            className="hidden md:block mr-3 p-2 rounded-lg"
            style={{ border: "none", background: "transparent", color: "var(--color-texto-secundario)", cursor: "pointer" }}
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

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
              {/* RR_00_11: sin cuenta el límite diario es menor. */}
              <span className="block mt-1">Con una cuenta tienes más consultas al día.</span>
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
                    cerrarMenu();
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

        {/*
          Pie: cuenta y consultas restantes, alineado con el área de la consulta.
          Con cuenta es una sola fila que abre el menú de la cuenta; el visitante
          ve los botones para entrar o registrarse.
        */}
        <div
          className="shrink-0 flex flex-col justify-end md:min-h-[max(var(--alto-pie-lateral,0px),var(--alto-pie-chat,0px))]"
          style={{ borderTop: "1px solid var(--color-borde)" }}
        >
          <div ref={pieRef} className="px-3 py-3">
            {autenticado && sesion?.usuario ? (
              <div ref={menuCuentaRef} className="relative">
                {menuCuentaAbierto && (
                  <div
                    id="menu-cuenta"
                    role="menu"
                    className="absolute bottom-full left-0 right-0 mb-2 rounded-xl p-1 flex flex-col gap-0.5 shadow-lg"
                    style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}
                  >
                    <OpcionDeMenu icono={User} activa={esPerfil} onClick={() => irA("/profile")}>
                      Mi perfil
                    </OpcionDeMenu>
                    {sesion.usuario.rol === "supermoderador" && (
                      <OpcionDeMenu icono={LayoutGrid} activa={esAdmin} onClick={() => irA("/admin")}>
                        Administración
                      </OpcionDeMenu>
                    )}
                    {/* RR_00_01 cerrar la sesión activa. */}
                    <OpcionDeMenu icono={LogOut} onClick={() => void manejarSalida()}>
                      Cerrar sesión
                    </OpcionDeMenu>
                  </div>
                )}
                <button
                  onClick={() => setMenuCuentaAbierto((abierto) => !abierto)}
                  aria-haspopup="menu"
                  aria-expanded={menuCuentaAbierto}
                  aria-controls="menu-cuenta"
                  className="flex items-center gap-3 w-full rounded-xl px-2 py-2 text-left transition-all"
                  style={{
                    background: menuCuentaAbierto || esPerfil || esAdmin ? "var(--color-superficie-marca)" : "transparent",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  <span
                    className="flex items-center justify-center rounded-full text-xs font-bold shrink-0"
                    style={{ width: 34, height: 34, background: "var(--color-marca)", color: "var(--color-sobre-marca)" }}
                    aria-hidden="true"
                  >
                    {iniciales(sesion.usuario.nombre, sesion.usuario.correo)}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-medium truncate" style={{ color: "var(--color-texto)" }}>
                      {sesion.usuario.nombre || sesion.usuario.correo}
                    </span>
                    <ContadorConsultas restantes={restantes} limite={limite} />
                  </span>
                  <ChevronsUpDown size={16} className="shrink-0" style={{ color: "var(--color-texto-tenue)" }} aria-hidden="true" />
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                <ContadorConsultas restantes={restantes} limite={limite} cargando={!sesion} conBarra />
                <div className="flex gap-2 mt-1">
                  <button
                    onClick={() => navigate("/login")}
                    className="flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all"
                    style={{ background: "var(--color-marca)", color: "var(--color-sobre-marca)", border: "none", cursor: "pointer" }}
                  >
                    Iniciar sesión
                  </button>
                  <button
                    onClick={() => navigate("/register")}
                    className="flex-1 px-3 py-2 rounded-lg text-sm transition-all"
                    style={{ background: "transparent", color: "var(--color-texto-marca)", border: "1px solid var(--color-borde-marca)", cursor: "pointer" }}
                  >
                    Crear cuenta
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>

      <main className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/*
          Barra superior con el botón de menú: siempre en pantallas chicas, y en
          pantallas grandes solo si la barra lateral está plegada.
        */}
        <div
          className={`flex items-center gap-3 px-4 py-2 border-b shrink-0 ${plegada ? "" : "md:hidden"}`}
          style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}
        >
          <button
            onClick={mostrarBarra}
            aria-label="Abrir el menú"
            aria-controls="barra-lateral"
            aria-expanded={menuAbierto}
            className="p-2 -ml-2 rounded-lg"
            style={{ border: "none", background: "transparent", color: "var(--color-texto)", cursor: "pointer" }}
          >
            <Menu size={20} />
          </button>
          <Logo tamano={28} redondeo={8} />
          <span className="font-semibold text-sm" style={{ color: "var(--color-texto)" }}>
            {NOMBRE_APP}
          </span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
