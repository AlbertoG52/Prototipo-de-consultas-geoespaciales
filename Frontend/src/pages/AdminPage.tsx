/**
 * Panel de administración
 *
 * "Usuarios" (RR_70 a RR_76, en components/admin/), "Respuestas" (RR_80),
 * "Roles y permisos" (tipos de consulta por rol, RR_77, y límites por rol,
 * RR_63 y RR_64), las tarjetas superiores y "Estadísticas" (RR_78) y
 * "Auditoría" (RR_00_09) usan datos reales; la ruta está protegida por rol
 * (RR_00_10). La tabla "Permisos por rol" es descriptiva.
 */
import { useCallback, useEffect, useState } from "react";

import { ClipboardList } from "lucide-react";
import { EstadisticasDeUso } from "../components/admin/EstadisticasDeUso";
import { HistorialDeUso } from "../components/admin/HistorialDeUso";
import { LimitesPorRol } from "../components/admin/LimitesPorRol";
import { PreferenciasPorDefecto } from "../components/admin/PreferenciasPorDefecto";
import { ResumenDeUso } from "../components/admin/ResumenDeUso";
import { TablaUsuarios } from "../components/admin/TablaUsuarios";
import { TiposDeConsultaPorRol } from "../components/admin/TiposDeConsultaPorRol";
import { UsoPorRol } from "../components/admin/UsoPorRol";
import { useAuth } from "../context/AuthContext";
import * as api from "../services/api";
import type { RegistroAuditoria, RolOut, UsoDeRol, Usuario } from "../types";
import { IDIOMA_FECHAS } from "../config/textos";

const ACCIONES: Record<string, string> = {
  cambio_rol: "Cambio de rol",
  cambio_estado: "Cambio de estado",
  cambio_limite: "Cambio de límite de consultas", // RR_63
  cambio_permiso: "Cambio de permisos", // RR_77: afecta a un rol, no a una cuenta
};

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
    { id: "respuestas", label: "Respuestas", icon: "🗺️" },
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

          <ResumenDeUso />

          {activeSection === "usuarios" && (
            <>
              {uso.length > 0 && <UsoPorRol uso={uso} />}
              {usoDe && <HistorialDeUso key={usoDe.id} usuario={users.find((u) => u.id === usoDe.id) ?? usoDe} alCerrar={() => setUsoDe(null)} />}
              <TablaUsuarios usuarios={users} miId={miId} alCambiar={(id, campo, valor) => void cambiar(id, campo, valor)} alVerUso={setUsoDe} />
            </>
          )}

          {activeSection === "roles" && (
            <div className="flex flex-col gap-4">
              <TiposDeConsultaPorRol />
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

          {activeSection === "respuestas" && <PreferenciasPorDefecto />}

          {activeSection === "estadisticas" && <EstadisticasDeUso />}

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
                        {/* Un cambio de límite (RR_63) o de permisos (RR_77) es de un rol, no de una cuenta: el detalle dice cuál. */}
                        {!["cambio_limite", "cambio_permiso"].includes(log.accion) && (
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
