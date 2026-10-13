/**
 * Usuarios registrados del panel de administración.
 *
 * - RR_71: correo, rol y estado de cada cuenta.
 * - RR_72: búsqueda por nombre o correo y filtro por rol, sobre el listado completo.
 * - RR_70: el rol se cambia desde su etiqueta.
 * - RR_74 / RR_75: desactivar y reactivar.
 * - RR_76: "Ver uso" abre el historial de consultas de la cuenta.
 *
 * La propia fila no tiene acciones; el servidor también lo rechaza (409).
 */
import { useState } from "react";

import { History } from "lucide-react";
import { CELDA_VACIA, ETIQUETAS_ROL } from "../../config/textos";
import type { NombreRol, Usuario } from "../../types";

const ROLES = Object.keys(ETIQUETAS_ROL) as NombreRol[];

const COLORES_ROL: Record<NombreRol, { fondo: string; texto: string }> = {
  supermoderador: { fondo: "var(--color-marca-fuerte)", texto: "var(--color-sobre-marca)" },
  moderador: { fondo: "var(--color-superficie-marca)", texto: "var(--color-texto-marca)" },
  usuario: { fondo: "var(--color-superficie-suave)", texto: "var(--color-texto-secundario)" },
};

const COLORES_ESTADO: Record<Usuario["estado"], { texto: string; punto: string }> = {
  activo: { texto: "var(--color-texto-marca)", punto: "var(--color-marca)" },
  inactivo: { texto: "var(--color-neutro)", punto: "var(--color-neutro)" },
};

const TODOS = "todos";

interface Props {
  usuarios: Usuario[];
  miId: number | undefined;
  /** Aplica un cambio de rol o de estado en el servidor. */
  alCambiar: (id: number, campo: "estado" | "rol", valor: string) => void;
  alVerUso: (usuario: Usuario) => void;
}

function iniciales(nombre: string): string {
  return nombre.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

export function TablaUsuarios({ usuarios, miId, alCambiar, alVerUso }: Props) {
  const [busqueda, setBusqueda] = useState("");
  const [filtroRol, setFiltroRol] = useState<NombreRol | typeof TODOS>(TODOS);
  const [editando, setEditando] = useState<number | null>(null);

  const texto = busqueda.toLowerCase();
  const filtrados = usuarios.filter(
    (u) =>
      ((u.nombre ?? "").toLowerCase().includes(texto) || u.correo.toLowerCase().includes(texto)) &&
      (filtroRol === TODOS || u.rol === filtroRol),
  );

  const cambiarRol = (id: number, rol: string) => {
    setEditando(null);
    alCambiar(id, "rol", rol);
  };

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
      <div className="px-6 py-4 border-b flex items-center gap-3 flex-wrap" style={{ borderColor: "var(--color-borde)" }}>
        <h2 className="font-semibold" style={{ color: "var(--color-texto)" }}>Usuarios registrados</h2>
        <div className="flex-1 min-w-48">
          <input
            type="text"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por nombre o correo..."
            aria-label="Buscar por nombre o correo"
            className="w-full rounded-xl px-3 py-2 text-sm outline-none"
            style={{ border: "1.5px solid var(--color-borde-fuerte)", background: "var(--color-fondo)", color: "var(--color-texto)" }}
            onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-borde-marca)"; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-borde-fuerte)"; }}
          />
        </div>
        <select
          value={filtroRol}
          onChange={(e) => setFiltroRol(e.target.value as NombreRol | typeof TODOS)}
          aria-label="Filtrar por rol"
          className="rounded-xl px-3 py-2 text-sm outline-none"
          style={{ border: "1.5px solid var(--color-borde-fuerte)", background: "var(--color-fondo)", color: "var(--color-texto-cuerpo)", cursor: "pointer" }}
        >
          <option value={TODOS}>Todos los roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{ETIQUETAS_ROL[r]}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead style={{ background: "var(--color-superficie-suave)" }}>
            <tr>
              {["Usuario", "Correo", "Rol", "Estado", "Acciones"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtrados.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-4 text-sm" style={{ color: "var(--color-texto-tenue)" }}>
                  Ningún usuario coincide con la búsqueda.
                </td>
              </tr>
            )}
            {filtrados.map((u) => {
              const esYo = u.id === miId;
              const nombre = u.nombre ?? u.correo;
              return (
                <tr key={u.id} style={{ borderTop: "1px solid var(--color-superficie-suave)" }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex items-center justify-center rounded-full text-xs font-bold" style={{ width: 32, height: 32, background: "var(--color-marca)", color: "var(--color-sobre-marca)", flexShrink: 0 }}>
                        {iniciales(nombre)}
                      </div>
                      <span className="font-medium" style={{ color: "var(--color-texto)" }}>{nombre}{esYo && " (tú)"}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--color-texto-secundario)" }}>{u.correo}</td>
                  <td className="px-4 py-3">
                    {editando === u.id ? (
                      <select
                        autoFocus
                        defaultValue={u.rol}
                        onChange={(e) => cambiarRol(u.id, e.target.value)}
                        onBlur={() => setEditando(null)}
                        aria-label={`Rol de ${nombre}`}
                        className="text-xs rounded-lg px-2 py-1 outline-none"
                        style={{ border: "1.5px solid var(--color-borde-marca)", background: "var(--color-superficie-suave)", color: "var(--color-texto)", cursor: "pointer" }}
                      >
                        {ROLES.map((r) => <option key={r} value={r}>{ETIQUETAS_ROL[r]}</option>)}
                      </select>
                    ) : (
                      <button
                        onClick={() => !esYo && setEditando(u.id)}
                        disabled={esYo}
                        title={esYo ? undefined : "Cambiar rol"}
                        className="text-xs px-2.5 py-1 rounded-full font-medium"
                        style={{ background: COLORES_ROL[u.rol].fondo, color: COLORES_ROL[u.rol].texto, border: "none", cursor: esYo ? "default" : "pointer" }}
                      >
                        {ETIQUETAS_ROL[u.rol]}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1.5 text-xs">
                      <span className="rounded-full" style={{ width: 6, height: 6, background: COLORES_ESTADO[u.estado].punto, display: "inline-block" }} />
                      <span style={{ color: COLORES_ESTADO[u.estado].texto }}>{u.estado}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => alVerUso(u)}
                        className="flex items-center gap-1 text-xs px-3 py-1 rounded-lg whitespace-nowrap"
                        style={{ background: "var(--color-superficie-suave)", color: "var(--color-texto-cuerpo)", border: "none", cursor: "pointer" }}
                      >
                        <History size={12} aria-hidden="true" />
                        Ver uso
                      </button>
                      {esYo ? (
                        <span className="text-xs px-3 py-1" style={{ color: "var(--color-borde-fuerte)" }}>{CELDA_VACIA}</span>
                      ) : (
                        <button
                          onClick={() => alCambiar(u.id, "estado", u.estado === "activo" ? "inactivo" : "activo")}
                          className="text-xs px-3 py-1 rounded-lg transition-all"
                          style={{ background: u.estado === "activo" ? "var(--color-error-fondo)" : "var(--color-superficie-marca)", color: u.estado === "activo" ? "var(--color-error)" : "var(--color-texto-marca)", border: "none", cursor: "pointer" }}
                        >
                          {u.estado === "activo" ? "Desactivar" : "Reactivar"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
