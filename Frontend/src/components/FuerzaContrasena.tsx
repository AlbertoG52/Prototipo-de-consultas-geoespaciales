/**
 * Reglas de contraseña e indicador de fuerza — RR_00_03.
 *
 * Son las mismas reglas que valida el servidor (Backend/app/schemas/usuario.py);
 * si cambian allá, hay que cambiarlas aquí. En el navegador solo guían a quien
 * escribe: el servidor rechaza igual una contraseña que no las cumpla.
 *
 * Lo usan el registro, el restablecimiento de contraseña (RR_00_06) y el
 * cambio de contraseña del perfil.
 */
import { Check, Dot } from "lucide-react";

export const REGLAS_PASSWORD = [
  { etiqueta: "Al menos 8 caracteres", cumple: (p: string) => p.length >= 8 },
  { etiqueta: "Una letra mayúscula", cumple: (p: string) => /[A-Z]/.test(p) },
  { etiqueta: "Un número", cumple: (p: string) => /\d/.test(p) },
  { etiqueta: "Un carácter especial o símbolo", cumple: (p: string) => /[^A-Za-z0-9]/.test(p) },
];

export const cumpleReglasPassword = (p: string) => REGLAS_PASSWORD.every((r) => r.cumple(p));

export function FuerzaContrasena({ password }: { password: string }) {
  const puntaje = REGLAS_PASSWORD.filter((r) => r.cumple(password)).length;
  const colores = ["var(--color-borde-fuerte)", "var(--color-aviso)", "var(--color-aviso)", "var(--color-exito)", "var(--color-marca)"];
  const etiquetas = ["", "Débil", "Regular", "Buena", "Fuerte"];

  return (
    <div className="mt-2">
      <div className="flex gap-1 mb-1.5">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex-1 rounded-full"
            style={{ height: 4, background: i < puntaje ? colores[puntaje] : "var(--color-superficie-marca)", transition: "background 0.3s" }}
          />
        ))}
      </div>
      {password && (
        <p className="text-xs mb-2" style={{ color: colores[puntaje] }}>
          {etiquetas[puntaje]}
        </p>
      )}
      <div className="flex flex-col gap-0.5" aria-label="Requisitos de la contraseña">
        {REGLAS_PASSWORD.map((r) => {
          const ok = r.cumple(password);
          return (
            <div key={r.etiqueta} className="flex items-center gap-1.5 text-xs" style={{ color: ok ? "var(--color-texto-marca)" : "var(--color-texto-tenue)" }}>
              {ok ? <Check size={12} strokeWidth={2.5} /> : <Dot size={12} strokeWidth={6} style={{ opacity: 0.3 }} />}
              {r.etiqueta}
            </div>
          );
        })}
      </div>
    </div>
  );
}
