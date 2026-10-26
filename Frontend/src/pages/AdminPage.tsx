/**
 * Panel de administración
 *
 * "Usuarios" (RR_70 a RR_76), "Roles y permisos" (límites por rol, RR_63 y
 * RR_64; componentes en components/admin/) y "Auditoría" (RR_00_09) usan datos
 * reales; la ruta está protegida por rol (RR_00_10). Las tarjetas superiores y
 * "Estadísticas" son de RR_78 y siguen con datos de ejemplo.
 */
import { useCallback, useEffect, useState } from "react";

import { ClipboardList } from "lucide-react";
import { HistorialDeUso } from "../components/admin/HistorialDeUso";
import { LimitesPorRol } from "../components/admin/LimitesPorRol";
import { TablaUsuarios } from "../components/admin/TablaUsuarios";
import { UsoPorRol } from "../components/admin/UsoPorRol";
import { useAuth } from "../context/AuthContext";
import * as api from "../services/api";
import type { RegistroAuditoria, RolOut, UsoDeRol, Usuario } from "../types";
import { IDIOMA_FECHAS } from "../config/textos";

const ACCIONES: Record<string, string> = {
  cambio_rol: "Cambio de rol",
  cambio_estado: "Cambio de estado",
  cambio_limite: "Cambio de límite de consultas", // RR_63
};

function DatosDeEjemplo() {
  return (
    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--color-aviso-fondo)", color: "var(--color-aviso-texto)" }}>
      Datos de ejemplo
    </span>
  );
}

const STATS = [
  { label: "Usuarios totales", value: "7", icon: "👥", change: "+2 este mes" },
  { label: "Consultas hoy", value: "143", icon: "💬", change: "+18 vs ayer" },
  { label: "Consultas este mes", value: "2,841", icon: "📊", change: "+12%" },
  { label: "Tasa de éxito", value: "96.4%", icon: "✅", change: "Estable" },
];

export function AdminPage() {
  const { sesion } = useAuth();
  const miId = sesion?.usuario?.id;
  const [users, setUsers] = useState<Usuario[]>([]);
  const [auditoria, setAuditoria] = useState<RegistroAuditoria[]>([]);
  const [uso, setUso] = useState<UsoDeRol[]>([]);
  const [usoDe, setUsoDe] = useState<Usuario | null>(null);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState("usuarios");
  const [roles, setRoles] = useState<RolOut[]>([]);

  const cargar = useCallback(async () => {
    try {
      const [u, a, r, l] = await Promise.all([
        api.listarUsuarios(),
        api.obtenerAuditoria(),
        api.obtenerUsoPorRol(),
        api.listarRoles(),
      ]);
      setUsers(u);
      setAuditoria(a);
      setUso(r);
      setRoles(l);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los datos.");
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  /** Aplica el cambio en el servidor y recarga usuarios, uso por rol y auditoría. */
  const cambiar = async (id: number, campo: "estado" | "rol", valor: string) => {
    setError("");
    try {
      await api.cambiarUsuario(id, campo, valor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo aplicar el cambio.");
    }
    await cargar();
  };

  const sections = [
    { id: "usuarios", label: "Usuarios", icon: "👥" },
    { id: "roles", label: "Roles y permisos", icon: "🔑" },
    { id: "estadisticas", label: "Estadísticas", icon: "📊" },
    { id: "auditoria", label: "Auditoría", icon: "📋" },
  ];

  return (
    <>
      {/* Header */}
      <div className="px-4 md:px-8 py-4 md:py-5 border-b shrink-0" style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}>
        <h1 className="text-xl font-semibold" style={{ color: "var(--color-texto)" }}>Panel de Administración</h1>
        <p className="text-sm" style={{ color: "var(--color-texto-secundario)" }}>Gestión de usuarios, roles y control de consultas — Supermoderador</p>
      </div>

      <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
        {/* Sub-nav: pestañas arriba en pantallas chicas, columna a la izquierda en grandes. */}
        <nav className="shrink-0 py-2 md:py-4 flex flex-row md:flex-col gap-1 overflow-x-auto border-b md:border-b-0 md:border-r md:w-[200px]" style={{ background: "var(--color-superficie)", borderColor: "var(--color-borde)" }}>
          {sections.map((s) => (
            <button key={s.id} onClick={() => setActiveSection(s.id)} className="flex items-center gap-2.5 mx-1 md:mx-2 px-3 py-2.5 rounded-lg text-sm text-left transition-all whitespace-nowrap shrink-0" style={{ background: activeSection === s.id ? "var(--color-superficie-marca)" : "transparent", color: activeSection === s.id ? "var(--color-texto)" : "var(--color-texto-secundario)", border: "none", cursor: "pointer", fontWeight: activeSection === s.id ? 500 : 400 }}>
              <span>{s.icon}</span>{s.label}
            </button>
          ))}
        </nav>

        {/* Content */}
        <div className="flex-1 min-w-0 overflow-y-auto p-4 md:p-6" style={{ background: "var(--color-fondo)" }}>

          {error && (
            <div className="rounded-xl px-4 py-3 mb-4 text-sm" style={{ background: "var(--color-error-fondo)", border: "1px solid var(--color-error-borde)", color: "var(--color-error-texto)" }}>
              {error}
            </div>
          )}

          {/* Stats row */}
          <div className="mb-2"><DatosDeEjemplo /></div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-2xl p-4" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>{s.label}</span>
                  <span style={{ fontSize: 20 }}>{s.icon}</span>
                </div>
                <div className="text-2xl font-bold" style={{ color: "var(--color-texto)" }}>{s.value}</div>
                <div className="text-xs mt-1" style={{ color: "var(--color-texto-suave)" }}>{s.change}</div>
              </div>
            ))}
          </div>

          {activeSection === "usuarios" && (
            <>
              {uso.length > 0 && <UsoPorRol uso={uso} />}
              {usoDe && <HistorialDeUso key={usoDe.id} usuario={users.find((u) => u.id === usoDe.id) ?? usoDe} alCerrar={() => setUsoDe(null)} />}
              <TablaUsuarios usuarios={users} miId={miId} alCambiar={(id, campo, valor) => void cambiar(id, campo, valor)} alVerUso={setUsoDe} />
            </>
          )}

          {activeSection === "roles" && (
            <div className="flex flex-col gap-4">
              <LimitesPorRol roles={roles} alGuardar={cargar} />
              <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
                <h2 className="font-semibold mb-4" style={{ color: "var(--color-texto)" }}>Permisos por rol</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ borderBottom: "2px solid var(--color-superficie-suave)" }}>
                        <th className="text-left py-2 pr-4 font-medium" style={{ color: "var(--color-texto-tenue)" }}>Permiso</th>
                        {["Usuario", "Moderador", "Supermoderador"].map((r) => (
                          <th key={r} className="text-center py-2 px-4 font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>{r}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ["Realizar consultas", true, true, true],
                        ["Ver historial propio", true, true, true],
                        ["Ver usuarios registrados", false, false, true],
                        ["Cambiar roles de usuarios", false, false, true],
                        ["Configurar límites por rol", false, false, true],
                        ["Ver auditoría del sistema", false, false, true],
                        ["Desactivar/reactivar cuentas", false, false, true],
                      ].map(([label, ...vals]) => (
                        <tr key={String(label)} style={{ borderBottom: "1px solid var(--color-superficie-suave)" }}>
                          <td className="py-2.5 pr-4" style={{ color: "var(--color-texto-cuerpo)" }}>{label}</td>
                          {vals.map((v, i) => (
                            <td key={i} className="text-center py-2.5 px-4">
                              {v ? (
                                <span style={{ color: "var(--color-texto-marca)" }}>✓</span>
                              ) : (
                                <span style={{ color: "var(--color-borde)" }}>—</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeSection === "estadisticas" && (
            <div className="flex flex-col gap-4">
              <div><DatosDeEjemplo /></div>
              <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
                <h2 className="font-semibold mb-4" style={{ color: "var(--color-texto)" }}>Uso del sistema por rol</h2>
                {[
                  { role: "supermoderador", count: 87, pct: 87, color: "var(--color-grafico-1)" },
                  { role: "moderador", count: 85, pct: 85, color: "var(--color-grafico-2)" },
                  { role: "usuario", count: 57, pct: 57, color: "var(--color-grafico-3)" },
                ].map((r) => (
                  <div key={r.role} className="mb-4">
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="capitalize font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>{r.role}</span>
                      <span style={{ color: "var(--color-texto-secundario)" }}>{r.count} consultas promedio</span>
                    </div>
                    <div className="rounded-full overflow-hidden" style={{ height: 8, background: "var(--color-superficie-suave)" }}>
                      <div className="h-full rounded-full" style={{ width: `${r.pct}%`, background: r.color, transition: "width 0.6s" }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
                  <h3 className="font-semibold mb-4 text-sm" style={{ color: "var(--color-texto)" }}>Consultas por día (última semana)</h3>
                  <div className="flex items-end gap-2" style={{ height: 80 }}>
                    {[32, 45, 28, 61, 38, 52, 43].map((h, i) => (
                      <div key={i} className="flex-1 rounded-t-md transition-all" style={{ height: `${(h / 61) * 100}%`, background: i === 6 ? "var(--color-marca)" : "var(--color-borde-fuerte)" }} title={`${h} consultas`} />
                    ))}
                  </div>
                  <div className="flex justify-between text-xs mt-2" style={{ color: "var(--color-texto-tenue)" }}>
                    {["L","M","X","J","V","S","D"].map((d) => <span key={d}>{d}</span>)}
                  </div>
                </div>
                <div className="rounded-2xl p-6" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
                  <h3 className="font-semibold mb-4 text-sm" style={{ color: "var(--color-texto)" }}>Tipos de consulta</h3>
                  {[
                    { label: "Distribución geoespacial", pct: 48, color: "var(--color-grafico-2)" },
                    { label: "Descripción de especie", pct: 31, color: "var(--color-grafico-3)" },
                    { label: "Hábitat y ecología", pct: 15, color: "var(--color-grafico-4)" },
                    { label: "Otras", pct: 6, color: "var(--color-grafico-5)" },
                  ].map((t) => (
                    <div key={t.label} className="flex items-center gap-2 mb-2 text-xs">
                      <div className="rounded-sm shrink-0" style={{ width: 10, height: 10, background: t.color }} />
                      <span style={{ color: "var(--color-texto-cuerpo)", flex: 1 }}>{t.label}</span>
                      <span className="font-medium" style={{ color: "var(--color-texto)" }}>{t.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === "auditoria" && (
            <div className="rounded-2xl overflow-hidden" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: "var(--color-borde)" }}>
                <h2 className="font-semibold" style={{ color: "var(--color-texto)" }}>Registro de auditoría</h2>
                <p className="text-xs mt-0.5" style={{ color: "var(--color-texto-tenue)" }}>Solo lectura. Acciones administrativas registradas del sistema.</p>
              </div>
              <div className="divide-y" style={{ borderColor: "var(--color-superficie-suave)" }}>
                {auditoria.length === 0 && (
                  <p className="px-6 py-4 text-sm" style={{ color: "var(--color-texto-tenue)" }}>Todavía no hay acciones registradas.</p>
                )}
                {auditoria.map((log) => (
                  <div key={log.id} className="px-6 py-4 flex items-start gap-4">
                    <div className="rounded-full p-2 shrink-0 mt-0.5" style={{ background: "var(--color-superficie-marca)" }}>
                      <ClipboardList size={12} style={{ color: "var(--color-texto-marca)" }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between flex-wrap gap-x-3 mb-0.5">
                        <span className="text-sm font-medium" style={{ color: "var(--color-texto)" }}>{ACCIONES[log.accion] ?? log.accion}</span>
                        <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>{new Date(log.fecha).toLocaleString(IDIOMA_FECHAS)}</span>
                      </div>
                      <div className="text-xs" style={{ color: "var(--color-texto-secundario)" }}>
                        {/* Un cambio de límite (RR_63) es de un rol, no de una cuenta: el detalle dice cuál. */}
                        {log.accion !== "cambio_limite" && (
                          <>Usuario afectado: <strong style={{ color: "var(--color-texto-cuerpo)" }}>{log.afectado ?? "—"}</strong> · </>
                        )}
                        Por: <strong style={{ color: "var(--color-texto-cuerpo)" }}>{log.actor ?? "Servidor"}</strong>
                      </div>
                      <div className="text-xs mt-0.5 font-mono break-words" style={{ color: "var(--color-texto-tenue)" }}>{log.detalle}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
