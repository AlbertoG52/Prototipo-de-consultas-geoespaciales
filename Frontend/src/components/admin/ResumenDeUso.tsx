/**
 * RR_78 — tarjetas del panel de administración (GET /admin/estadisticas/resumen).
 *
 * Cuentas registradas y consultas de hoy y de los últimos 30 días, contadas
 * igual que en "Estadísticas" (visitantes incluidos). Se ven en todas las
 * secciones del panel y se recargan cada 30 s mientras la pestaña está visible.
 */
import { useCallback, useState } from "react";

import { CalendarDays, CircleCheck, MessageSquare, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { CELDA_VACIA, formatearNumero, formatearPorcentaje } from "../../config/textos";
import { useRecargaAutomatica } from "../../hooks/useRecargaAutomatica";
import * as api from "../../services/api";
import type { ResumenUso } from "../../types";

const RECARGA_MS = 30_000; // RR_78 criterio 3

type Tarjeta = { titulo: string; valor: string; detalle: string; Icono: LucideIcon };

function tarjetas(resumen: ResumenUso): Tarjeta[] {
  return [
    {
      titulo: "Usuarios registrados",
      valor: formatearNumero(resumen.usuarios),
      detalle: `+${formatearNumero(resumen.usuarios_nuevos_30_dias)} en los últimos 30 días`,
      Icono: Users,
    },
    {
      titulo: "Consultas hoy",
      valor: formatearNumero(resumen.consultas_hoy),
      detalle: `Ayer: ${formatearNumero(resumen.consultas_ayer)}`,
      Icono: MessageSquare,
    },
    {
      titulo: "Consultas en 30 días",
      valor: formatearNumero(resumen.consultas_30_dias),
      detalle: "Cuentas y visitantes",
      Icono: CalendarDays,
    },
    {
      titulo: "Tasa de éxito",
      valor: resumen.tasa_exito_30_dias === null ? CELDA_VACIA : formatearPorcentaje(resumen.tasa_exito_30_dias),
      detalle: "Resueltas, últimos 30 días",
      Icono: CircleCheck,
    },
  ];
}

export function ResumenDeUso() {
  const [resumen, setResumen] = useState<ResumenUso | null>(null);
  const [error, setError] = useState(false);

  const cargar = useCallback(() => {
    api
      .obtenerResumenDeUso()
      .then((r) => {
        setResumen(r);
        setError(false);
      })
      .catch(() => setError(true));
  }, []);
  useRecargaAutomatica(cargar, RECARGA_MS);

  if (!resumen) {
    return error ? (
      <p role="alert" className="text-xs mb-6" style={{ color: "var(--color-error-texto)" }}>
        No se pudieron cargar las cifras del sistema.
      </p>
    ) : null;
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {tarjetas(resumen).map(({ titulo, valor, detalle, Icono }) => (
        <div key={titulo} className="rounded-2xl p-4" style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde)" }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>{titulo}</span>
            <Icono size={18} aria-hidden style={{ color: "var(--color-texto-marca)" }} />
          </div>
          <div className="text-2xl font-bold" style={{ color: "var(--color-texto)" }}>{valor}</div>
          <div className="text-xs mt-1" style={{ color: "var(--color-texto-suave)" }}>{detalle}</div>
        </div>
      ))}
    </div>
  );
}
