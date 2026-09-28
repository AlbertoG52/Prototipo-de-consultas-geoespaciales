/**
 * Perfil del usuario.
 *
 * Corresponde al módulo 4 (RR_66, RR_67, RR_68, RR_76) y a RR_00_03 /
 * RR_00_04.  Ningún dato de esta pantalla viene del servidor todavía
 * solo existe la interfaz.
 */
import { useState } from "react";

export function ProfilePage() {
  const [name, setName] = useState("María González");
  const [email] = useState("maria.gonzalez@gmail.com");
  const [saved, setSaved] = useState(false);
  const [showMap, setShowMap] = useState(true);
  const [showSources, setShowSources] = useState(true);
  const [inactivityTimeout, setInactivityTimeout] = useState("30m");
  const [activeTab, setActiveTab] = useState("perfil");

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const tabs = [
    { id: "perfil", label: "Perfil" },
    { id: "preferencias", label: "Preferencias" },
    { id: "historial", label: "Historial de uso" },
    { id: "seguridad", label: "Seguridad" },
  ];

  const HISTORY = [
    { query: "¿Dónde se encuentra la guaria morada?", date: "hoy 09:14", type: "distribución", status: "exitosa" },
    { query: "Plantas medicinales del Pacífico Sur", date: "ayer 16:40", type: "descripción", status: "exitosa" },
    { query: "Flora endémica de la Isla del Coco", date: "lun 11:22", type: "distribución", status: "exitosa" },
    { query: "¿Cuál es el árbol nacional de Costa Rica?", date: "lun 10:05", type: "descripción", status: "exitosa" },
    { query: "Hábitat del pejibaye", date: "dom 14:50", type: "hábitat", status: "sin datos" },
    { query: "orchideas costaricencez", date: "sáb 08:30", type: "descripción", status: "corregida" },
  ];

  return (
    <>
      {/* Header */}
      <div className="px-8 py-5 border-b shrink-0" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        <h1 className="text-xl font-semibold" style={{ color: "#1e3d2a" }}>Mi perfil</h1>
        <p className="text-sm" style={{ color: "#6b8f74" }}>Gestiona tu cuenta y preferencias de consulta</p>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ background: "#f7f8f5" }}>
        {/* Profile hero */}
        <div className="px-8 py-8" style={{ background: "#ffffff", borderBottom: "1px solid #dde8df" }}>
          <div className="flex items-center gap-5 max-w-2xl">
            <div className="flex items-center justify-center rounded-full text-2xl font-bold" style={{ width: 72, height: 72, background: "#2d5a3d", color: "#fff", flexShrink: 0 }}>
              MG
            </div>
            <div>
              <h2 className="text-xl font-bold" style={{ color: "#1e3d2a", fontFamily: "'Lora', serif" }}>{name}</h2>
              <p className="text-sm" style={{ color: "#6b8f74" }}>{email}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ background: "#e8f0eb", color: "#2d5a3d" }}>usuario</span>
                <span className="text-xs px-2.5 py-1 rounded-full" style={{ background: "#f0f5f1", color: "#8aab92" }}>Cuenta verificada</span>
              </div>
            </div>
            <div className="ml-auto rounded-2xl p-4 text-center" style={{ background: "#f0f5f1", minWidth: 120 }}>
              <div className="text-2xl font-bold" style={{ color: "#1e3d2a" }}>18</div>
              <div className="text-xs" style={{ color: "#8aab92" }}>consultas restantes</div>
              <div className="rounded-full overflow-hidden mt-2" style={{ height: 4, background: "#c5dccb" }}>
                <div className="h-full rounded-full" style={{ width: "90%", background: "#2d5a3d" }} />
              </div>
              <div className="text-xs mt-1" style={{ color: "#a8d4b0" }}>de 20 hoy</div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b px-8" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
          <div className="flex gap-0 max-w-2xl">
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setActiveTab(t.id)} className="px-5 py-3.5 text-sm font-medium transition-all" style={{ border: "none", background: "transparent", cursor: "pointer", borderBottom: activeTab === t.id ? "2px solid #2d5a3d" : "2px solid transparent", color: activeTab === t.id ? "#2d5a3d" : "#8aab92", marginBottom: -1 }}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="px-8 py-6 max-w-2xl">
          {activeTab === "perfil" && (
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h3 className="font-semibold mb-4" style={{ color: "#1e3d2a" }}>Información personal</h3>
                {saved && (
                  <div className="flex items-center gap-2 rounded-xl p-3 mb-4 text-sm" style={{ background: "#e8f0eb", border: "1px solid #c5dccb", color: "#2d5a3d" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    Cambios guardados correctamente.
                  </div>
                )}
                <div className="flex flex-col gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>Nombre completo</label>
                    <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-xl px-4 py-3 text-sm outline-none" style={{ border: "1.5px solid #c5dccb", background: "#f7f8f5", color: "#1e3d2a" }}
                      onFocus={(e) => { e.currentTarget.style.borderColor = "#2d5a3d"; e.currentTarget.style.background = "#fff"; }}
                      onBlur={(e) => { e.currentTarget.style.borderColor = "#c5dccb"; e.currentTarget.style.background = "#f7f8f5"; }}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>Correo electrónico</label>
                    <input type="email" value={email} disabled className="w-full rounded-xl px-4 py-3 text-sm" style={{ border: "1.5px solid #e8f0eb", background: "#f0f5f1", color: "#8aab92", cursor: "not-allowed" }} />
                    <p className="text-xs mt-1" style={{ color: "#a8d4b0" }}>El correo electrónico no se puede cambiar.</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>Rol</label>
                    <input type="text" value="usuario" disabled className="w-full rounded-xl px-4 py-3 text-sm" style={{ border: "1.5px solid #e8f0eb", background: "#f0f5f1", color: "#8aab92", cursor: "not-allowed" }} />
                    <p className="text-xs mt-1" style={{ color: "#a8d4b0" }}>El rol lo asigna el administrador del sistema.</p>
                  </div>
                  <button onClick={handleSave} className="self-start px-5 py-2.5 rounded-xl text-sm font-medium" style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}>
                    Guardar cambios
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === "preferencias" && (
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h3 className="font-semibold mb-1" style={{ color: "#1e3d2a" }}>Configuración de respuestas</h3>
                <p className="text-xs mb-4" style={{ color: "#8aab92" }}>Personaliza cómo el agente presenta los resultados de tus consultas.</p>
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "#f0f5f1" }}>
                    <div>
                      <div className="text-sm font-medium" style={{ color: "#1e3d2a" }}>Incluir mapa de distribución</div>
                      <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>Muestra el mapa geoespacial junto a la respuesta cuando hay datos disponibles.</div>
                    </div>
                    <button onClick={() => setShowMap((v) => !v)} className="relative rounded-full transition-all" style={{ width: 44, height: 24, background: showMap ? "#2d5a3d" : "#c5dccb", border: "none", cursor: "pointer", flexShrink: 0 }}>
                      <span className="absolute rounded-full transition-all" style={{ width: 18, height: 18, background: "#fff", top: 3, left: showMap ? 23 : 3, boxShadow: "0 1px 3px rgba(0,0,0,0.2)" }} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "#f0f5f1" }}>
                    <div>
                      <div className="text-sm font-medium" style={{ color: "#1e3d2a" }}>Mostrar fuentes de información</div>
                      <div className="text-xs mt-0.5" style={{ color: "#8aab92" }}>Lista las fuentes utilizadas (GBIF, Manual de Plantas de CR) al final de cada respuesta.</div>
                    </div>
                    <button onClick={() => setShowSources((v) => !v)} className="relative rounded-full transition-all" style={{ width: 44, height: 24, background: showSources ? "#2d5a3d" : "#c5dccb", border: "none", cursor: "pointer", flexShrink: 0 }}>
                      <span className="absolute rounded-full transition-all" style={{ width: 18, height: 18, background: "#fff", top: 3, left: showSources ? 23 : 3, boxShadow: "0 1px 3px rgba(0,0,0,0.2)" }} />
                    </button>
                  </div>
                </div>
                <button onClick={handleSave} className="mt-4 self-start px-5 py-2.5 rounded-xl text-sm font-medium" style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}>
                  Guardar preferencias
                </button>
              </div>
            </div>
          )}

          {activeTab === "historial" && (
            <div className="rounded-2xl overflow-hidden" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: "#dde8df" }}>
                <h3 className="font-semibold" style={{ color: "#1e3d2a" }}>Historial de consultas</h3>
                <p className="text-xs mt-0.5" style={{ color: "#8aab92" }}>Consultas realizadas en la sesión activa, en orden cronológico.</p>
              </div>
              <div className="divide-y" style={{ borderColor: "#f0f5f1" }}>
                {HISTORY.map((h, i) => (
                  <div key={i} className="px-6 py-3.5 flex items-center gap-3">
                    <div className="flex-1">
                      <div className="text-sm" style={{ color: "#374a3c" }}>{h.query}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs" style={{ color: "#8aab92" }}>{h.date}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#f0f5f1", color: "#6b8f74" }}>{h.type}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full" style={{
                          background: h.status === "exitosa" ? "#e8f0eb" : h.status === "corregida" ? "#fef9c3" : "#f5f5f5",
                          color: h.status === "exitosa" ? "#2d5a3d" : h.status === "corregida" ? "#854d0e" : "#9ca3af"
                        }}>{h.status}</span>
                      </div>
                    </div>
                    <button className="text-xs px-3 py-1.5 rounded-lg" style={{ background: "#f0f5f1", color: "#6b8f74", border: "none", cursor: "pointer" }}>
                      Repetir
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "seguridad" && (
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h3 className="font-semibold mb-4" style={{ color: "#1e3d2a" }}>Cambiar contraseña</h3>
                <div className="flex flex-col gap-3">
                  {["Contraseña actual", "Nueva contraseña", "Confirmar nueva contraseña"].map((label) => (
                    <div key={label}>
                      <label className="block text-sm font-medium mb-1.5" style={{ color: "#374a3c" }}>{label}</label>
                      <input type="password" placeholder="••••••••" className="w-full rounded-xl px-4 py-3 text-sm outline-none" style={{ border: "1.5px solid #c5dccb", background: "#f7f8f5", color: "#1e3d2a" }}
                        onFocus={(e) => { e.currentTarget.style.borderColor = "#2d5a3d"; e.currentTarget.style.background = "#fff"; }}
                        onBlur={(e) => { e.currentTarget.style.borderColor = "#c5dccb"; e.currentTarget.style.background = "#f7f8f5"; }}
                      />
                    </div>
                  ))}
                  <button className="self-start px-5 py-2.5 rounded-xl text-sm font-medium mt-1" style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}>
                    Actualizar contraseña
                  </button>
                </div>
              </div>
              <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                <h3 className="font-semibold mb-1" style={{ color: "#1e3d2a" }}>Tiempo de inactividad</h3>
                <p className="text-xs mb-4" style={{ color: "#8aab92" }}>Elige cuánto tiempo debe pasar sin actividad para cerrar la sesión automáticamente.</p>
                <div className="flex flex-col gap-2">
                  {[
                    { label: "30 minutos", value: "30m" },
                    { label: "1 hora", value: "1h" },
                    { label: "6 horas", value: "6h" },
                    { label: "12 horas", value: "12h" },
                    { label: "24 horas", value: "24h" },
                    { label: "1 semana", value: "1w" },
                    { label: "Nunca", value: "never" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all" style={{ background: inactivityTimeout === opt.value ? "#e8f0eb" : "#f0f5f1", border: `1.5px solid ${inactivityTimeout === opt.value ? "#2d5a3d" : "transparent"}` }}>
                      <input
                        type="radio"
                        name="inactivity"
                        value={opt.value}
                        checked={inactivityTimeout === opt.value}
                        onChange={() => setInactivityTimeout(opt.value)}
                        style={{ accentColor: "#2d5a3d" }}
                      />
                      <span className="text-sm" style={{ color: inactivityTimeout === opt.value ? "#1e3d2a" : "#374a3c", fontWeight: inactivityTimeout === opt.value ? 500 : 400 }}>
                        {opt.label}
                      </span>
                      {opt.value === "30m" && <span className="text-xs ml-auto" style={{ color: "#8aab92" }}>Recomendado</span>}
                    </label>
                  ))}
                </div>
                <button onClick={handleSave} className="mt-4 px-5 py-2.5 rounded-xl text-sm font-medium" style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}>
                  Guardar configuración
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
