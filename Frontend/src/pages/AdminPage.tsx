/**
 * Panel de administración
 *
 * Corresponde al módulo 4 (RR_69 a RR_78). Se conserva con datos de
 * ejemplo. La ruta ya está protegida en Root: solo aparece en la barra
 * lateral si el rol de la sesión es supermoderador.
 */
import { useState } from "react";

const USERS = [
  { id: 1, name: "Ana Rodríguez", email: "ana.rodriguez@tec.ac.cr", role: "supermoderador", status: "activo", queries: 87, lastQuery: "hace 5 min" },
  { id: 2, name: "Carlos Méndez", email: "carlos.mendez@tec.ac.cr", role: "moderador", status: "activo", queries: 54, lastQuery: "hace 2 h" },
  { id: 3, name: "María González", email: "maria.gonzalez@gmail.com", role: "usuario", status: "activo", queries: 18, lastQuery: "ayer" },
  { id: 4, name: "José Vargas", email: "jose.vargas@ucr.ac.cr", role: "usuario", status: "activo", queries: 12, lastQuery: "lun" },
  { id: 5, name: "Laura Brenes", email: "laura.brenes@gmail.com", role: "moderador", status: "inactivo", queries: 31, lastQuery: "hace 3 días" },
  { id: 6, name: "Diego Solís", email: "diego.solis@tec.ac.cr", role: "usuario", status: "inactivo", queries: 5, lastQuery: "hace 1 sem" },
  { id: 7, name: "Sofía Castro", email: "sofia.castro@gmail.com", role: "usuario", status: "activo", queries: 22, lastQuery: "hoy" },
];

const STATS = [
  { label: "Usuarios totales", value: "7", icon: "👥", change: "+2 este mes" },
  { label: "Consultas hoy", value: "143", icon: "💬", change: "+18 vs ayer" },
  { label: "Consultas este mes", value: "2,841", icon: "📊", change: "+12%" },
  { label: "Tasa de éxito", value: "96.4%", icon: "✅", change: "Estable" },
];

const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  supermoderador: { bg: "#1e3d2a", text: "#ffffff" },
  moderador: { bg: "#e8f0eb", text: "#2d5a3d" },
  usuario: { bg: "#f0f5f1", text: "#6b8f74" },
};

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  activo: { bg: "#e8f0eb", text: "#2d5a3d", dot: "#2d5a3d" },
  inactivo: { bg: "#f5f5f5", text: "#9ca3af", dot: "#9ca3af" },
};

export function AdminPage() {
  const [users, setUsers] = useState(USERS);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("todos");
  const [activeSection, setActiveSection] = useState("usuarios");
  const [editingUser, setEditingUser] = useState<number | null>(null);
  const [limitConfig, setLimitConfig] = useState({ usuario: 20, moderador: 100, supermoderador: 1000 });

  const filtered = users.filter((u) => {
    const matchSearch = u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase());
    const matchRole = roleFilter === "todos" || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  const toggleStatus = (id: number) => {
    setUsers((prev) => prev.map((u) => u.id === id ? { ...u, status: u.status === "activo" ? "inactivo" : "activo" } : u));
  };

  const changeRole = (id: number, role: string) => {
    setUsers((prev) => prev.map((u) => u.id === id ? { ...u, role } : u));
    setEditingUser(null);
  };

  const sections = [
    { id: "usuarios", label: "Usuarios", icon: "👥" },
    { id: "roles", label: "Roles y permisos", icon: "🔑" },
    { id: "estadisticas", label: "Estadísticas", icon: "📊" },
    { id: "auditoria", label: "Auditoría", icon: "📋" },
  ];

  const AUDIT_LOG = [
    { action: "Cambio de rol", user: "Laura Brenes", by: "Ana Rodríguez", date: "hoy 14:32", detail: "usuario → moderador" },
    { action: "Cuenta desactivada", user: "Diego Solís", by: "Ana Rodríguez", date: "ayer 09:15", detail: "estado: activo → inactivo" },
    { action: "Límite actualizado", user: "Sistema", by: "Ana Rodríguez", date: "lun 16:00", detail: "usuario: 15 → 20 consultas" },
    { action: "Reactivación", user: "Pedro Mora", by: "Ana Rodríguez", date: "vie 11:30", detail: "estado: inactivo → activo" },
  ];

  return (
    <>
      {/* Header */}
      <div className="px-8 py-5 border-b shrink-0" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        <h1 className="text-xl font-semibold" style={{ color: "#1e3d2a" }}>Panel de Administración</h1>
        <p className="text-sm" style={{ color: "#6b8f74" }}>Gestión de usuarios, roles y control de consultas — Supermoderador</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sub-nav */}
        <nav className="shrink-0 py-4 flex flex-col gap-1 border-r" style={{ width: 200, background: "#ffffff", borderColor: "#dde8df" }}>
          {sections.map((s) => (
            <button key={s.id} onClick={() => setActiveSection(s.id)} className="flex items-center gap-2.5 mx-2 px-3 py-2.5 rounded-lg text-sm text-left transition-all" style={{ background: activeSection === s.id ? "#e8f0eb" : "transparent", color: activeSection === s.id ? "#1e3d2a" : "#6b8f74", border: "none", cursor: "pointer", fontWeight: activeSection === s.id ? 500 : 400 }}>
              <span>{s.icon}</span>{s.label}
            </button>
          ))}
        </nav>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "#f7f8f5" }}>

          {/* Stats row */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-2xl p-4" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs" style={{ color: "#8aab92" }}>{s.label}</span>
                  <span style={{ fontSize: 20 }}>{s.icon}</span>
                </div>
                <div className="text-2xl font-bold" style={{ color: "#1e3d2a" }}>{s.value}</div>
                <div className="text-xs mt-1" style={{ color: "#a8d4b0" }}>{s.change}</div>
              </div>
            ))}
          </div>

          {activeSection === "usuarios" && (
            <div className="rounded-2xl overflow-hidden" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <div className="px-6 py-4 border-b flex items-center gap-3 flex-wrap" style={{ borderColor: "#dde8df" }}>
                <h2 className="font-semibold" style={{ color: "#1e3d2a" }}>Usuarios registrados</h2>
                <div className="flex-1 min-w-48">
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Buscar por nombre o correo..."
                    className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                    style={{ border: "1.5px solid #c5dccb", background: "#f7f8f5", color: "#1e3d2a" }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#2d5a3d"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#c5dccb"; }}
                  />
                </div>
                <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="rounded-xl px-3 py-2 text-sm outline-none" style={{ border: "1.5px solid #c5dccb", background: "#f7f8f5", color: "#374a3c", cursor: "pointer" }}>
                  <option value="todos">Todos los roles</option>
                  <option value="usuario">Usuario</option>
                  <option value="moderador">Moderador</option>
                  <option value="supermoderador">Supermoderador</option>
                </select>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead style={{ background: "#f0f5f1" }}>
                    <tr>
                      {["Usuario", "Correo", "Rol", "Estado", "Consultas", "Última actividad", "Acciones"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium" style={{ color: "#374a3c" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((u) => (
                      <tr key={u.id} style={{ borderTop: "1px solid #f0f5f1" }}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className="flex items-center justify-center rounded-full text-xs font-bold" style={{ width: 32, height: 32, background: "#2d5a3d", color: "#fff", flexShrink: 0 }}>
                              {u.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                            </div>
                            <span className="font-medium" style={{ color: "#1e3d2a" }}>{u.name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs" style={{ color: "#6b8f74" }}>{u.email}</td>
                        <td className="px-4 py-3">
                          {editingUser === u.id ? (
                            <select autoFocus defaultValue={u.role} onChange={(e) => changeRole(u.id, e.target.value)} onBlur={() => setEditingUser(null)} className="text-xs rounded-lg px-2 py-1 outline-none" style={{ border: "1.5px solid #2d5a3d", background: "#f0f5f1", color: "#1e3d2a", cursor: "pointer" }}>
                              {["usuario", "moderador", "supermoderador"].map((r) => <option key={r} value={r}>{r}</option>)}
                            </select>
                          ) : (
                            <button onClick={() => setEditingUser(u.id)} className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ background: ROLE_COLORS[u.role].bg, color: ROLE_COLORS[u.role].text, border: "none", cursor: "pointer" }}>
                              {u.role}
                            </button>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="flex items-center gap-1.5 text-xs">
                            <span className="rounded-full" style={{ width: 6, height: 6, background: STATUS_COLORS[u.status].dot, display: "inline-block" }} />
                            <span style={{ color: STATUS_COLORS[u.status].text }}>{u.status}</span>
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs" style={{ color: "#374a3c" }}>{u.queries}</td>
                        <td className="px-4 py-3 text-xs" style={{ color: "#8aab92" }}>{u.lastQuery}</td>
                        <td className="px-4 py-3">
                          {u.role === "supermoderador" ? (
                            <span className="text-xs px-3 py-1 rounded-lg" style={{ color: "#c5dccb", background: "transparent" }}>—</span>
                          ) : (
                            <button onClick={() => toggleStatus(u.id)} className="text-xs px-3 py-1 rounded-lg transition-all" style={{ background: u.status === "activo" ? "#fef3f2" : "#e8f0eb", color: u.status === "activo" ? "#dc2626" : "#2d5a3d", border: "none", cursor: "pointer" }}>
                              {u.status === "activo" ? "Desactivar" : "Reactivar"}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeSection === "roles" && (
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h2 className="font-semibold mb-4" style={{ color: "#1e3d2a" }}>Límite de consultas por rol</h2>
                <p className="text-xs mb-5" style={{ color: "#8aab92" }}>Define cuántas consultas puede realizar cada rol. El límite se restablece periódicamente.</p>
                <div className="flex flex-col gap-4">
                  {(Object.entries(limitConfig) as [keyof typeof limitConfig, number][]).map(([role, limit]) => (
                    <div key={role} className="flex items-center gap-4 p-4 rounded-xl" style={{ background: "#f0f5f1" }}>
                      <div className="flex-1">
                        <div className="text-sm font-medium capitalize" style={{ color: "#1e3d2a" }}>{role}</div>
                        <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>
                          {role === "usuario" ? "Cuenta creada mediante registro público" : role === "moderador" ? "Acceso extendido con configuración adicional" : "Acceso total al sistema"}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          value={limit}
                          onChange={(e) => setLimitConfig((c) => ({ ...c, [role]: +e.target.value }))}
                          min={1}
                          className="rounded-xl px-3 py-2 text-sm text-center outline-none font-medium"
                          style={{ width: 80, border: "1.5px solid #c5dccb", background: "#fff", color: "#1e3d2a" }}
                          onFocus={(e) => { e.currentTarget.style.borderColor = "#2d5a3d"; }}
                          onBlur={(e) => { e.currentTarget.style.borderColor = "#c5dccb"; }}
                        />
                        <span className="text-xs" style={{ color: "#6b8f74" }}>consultas/día</span>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="mt-4 px-5 py-2.5 rounded-xl text-sm font-medium" style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}>
                  Guardar configuración
                </button>
              </div>
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h2 className="font-semibold mb-4" style={{ color: "#1e3d2a" }}>Permisos por rol</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ borderBottom: "2px solid #f0f5f1" }}>
                        <th className="text-left py-2 pr-4 font-medium" style={{ color: "#8aab92" }}>Permiso</th>
                        {["Usuario", "Moderador", "Supermoderador"].map((r) => (
                          <th key={r} className="text-center py-2 px-4 font-medium" style={{ color: "#374a3c" }}>{r}</th>
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
                        <tr key={String(label)} style={{ borderBottom: "1px solid #f0f5f1" }}>
                          <td className="py-2.5 pr-4" style={{ color: "#374a3c" }}>{label}</td>
                          {vals.map((v, i) => (
                            <td key={i} className="text-center py-2.5 px-4">
                              {v ? (
                                <span style={{ color: "#2d5a3d" }}>✓</span>
                              ) : (
                                <span style={{ color: "#dde8df" }}>—</span>
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
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h2 className="font-semibold mb-4" style={{ color: "#1e3d2a" }}>Uso del sistema por rol</h2>
                {[
                  { role: "supermoderador", count: 87, pct: 87, color: "#1e3d2a" },
                  { role: "moderador", count: 85, pct: 85, color: "#2d5a3d" },
                  { role: "usuario", count: 57, pct: 57, color: "#4a8c5c" },
                ].map((r) => (
                  <div key={r.role} className="mb-4">
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="capitalize font-medium" style={{ color: "#374a3c" }}>{r.role}</span>
                      <span style={{ color: "#6b8f74" }}>{r.count} consultas promedio</span>
                    </div>
                    <div className="rounded-full overflow-hidden" style={{ height: 8, background: "#f0f5f1" }}>
                      <div className="h-full rounded-full" style={{ width: `${r.pct}%`, background: r.color, transition: "width 0.6s" }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                  <h3 className="font-semibold mb-4 text-sm" style={{ color: "#1e3d2a" }}>Consultas por día (última semana)</h3>
                  <div className="flex items-end gap-2" style={{ height: 80 }}>
                    {[32, 45, 28, 61, 38, 52, 43].map((h, i) => (
                      <div key={i} className="flex-1 rounded-t-md transition-all" style={{ height: `${(h / 61) * 100}%`, background: i === 6 ? "#2d5a3d" : "#c5dccb" }} title={`${h} consultas`} />
                    ))}
                  </div>
                  <div className="flex justify-between text-xs mt-2" style={{ color: "#8aab92" }}>
                    {["L","M","X","J","V","S","D"].map((d) => <span key={d}>{d}</span>)}
                  </div>
                </div>
                <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                  <h3 className="font-semibold mb-4 text-sm" style={{ color: "#1e3d2a" }}>Tipos de consulta</h3>
                  {[
                    { label: "Distribución geoespacial", pct: 48, color: "#2d5a3d" },
                    { label: "Descripción de especie", pct: 31, color: "#4a8c5c" },
                    { label: "Hábitat y ecología", pct: 15, color: "#a8d4b0" },
                    { label: "Otras", pct: 6, color: "#dde8df" },
                  ].map((t) => (
                    <div key={t.label} className="flex items-center gap-2 mb-2 text-xs">
                      <div className="rounded-sm shrink-0" style={{ width: 10, height: 10, background: t.color }} />
                      <span style={{ color: "#374a3c", flex: 1 }}>{t.label}</span>
                      <span className="font-medium" style={{ color: "#1e3d2a" }}>{t.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === "auditoria" && (
            <div className="rounded-2xl overflow-hidden" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: "#dde8df" }}>
                <h2 className="font-semibold" style={{ color: "#1e3d2a" }}>Registro de auditoría</h2>
                <p className="text-xs mt-0.5" style={{ color: "#8aab92" }}>Solo lectura. Acciones administrativas registradas del sistema.</p>
              </div>
              <div className="divide-y" style={{ borderColor: "#f0f5f1" }}>
                {AUDIT_LOG.map((log, i) => (
                  <div key={i} className="px-6 py-4 flex items-start gap-4">
                    <div className="rounded-full p-2 shrink-0 mt-0.5" style={{ background: "#e8f0eb" }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" stroke="#2d5a3d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-sm font-medium" style={{ color: "#1e3d2a" }}>{log.action}</span>
                        <span className="text-xs" style={{ color: "#8aab92" }}>{log.date}</span>
                      </div>
                      <div className="text-xs" style={{ color: "#6b8f74" }}>
                        Usuario afectado: <strong style={{ color: "#374a3c" }}>{log.user}</strong> · Por: <strong style={{ color: "#374a3c" }}>{log.by}</strong>
                      </div>
                      <div className="text-xs mt-0.5 font-mono" style={{ color: "#8aab92" }}>{log.detail}</div>
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
