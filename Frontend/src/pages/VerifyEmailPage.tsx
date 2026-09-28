/**
 *
 * Corresponde a RR_00_07 (Verificación de correo)
 */
import { useNavigate } from "react-router";

export function VerifyEmailPage() {
  const navigate = useNavigate();

  return (
    <div
      className="min-h-full flex items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #e8f0eb 0%, #f7f8f5 50%, #d4e8da 100%)" }}
    >
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center rounded-2xl mb-4" style={{ width: 64, height: 64, background: "#2d5a3d" }}>
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 2C8 2 5 6 5 10c0 3 1.5 5.5 4 7l1 4h4l1-4c2.5-1.5 4-4 4-7 0-4-3-8-7-8z" fill="white" opacity="0.9" />
              <path d="M12 6v10M9 9l3-3 3 3M9 13l3 3 3-3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "#1e3d2a", fontFamily: "'Lora', serif" }}>
            FloraBot CR
          </h1>
        </div>

        <div
          className="rounded-2xl p-8"
          style={{ background: "#ffffff", border: "1px solid #dde8df", boxShadow: "0 4px 24px rgba(45,90,61,0.08)" }}
        >
          <div className="flex items-center justify-center mb-5">
            <div className="rounded-full p-3" style={{ background: "#e8f0eb" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <rect x="2" y="4" width="20" height="16" rx="2" stroke="#2d5a3d" strokeWidth="1.8" />
                <path d="M2 8l10 6 10-6" stroke="#2d5a3d" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </div>
          </div>

          <h2 className="text-lg font-semibold text-center mb-2" style={{ color: "#1e3d2a" }}>
            Verificar tu correo
          </h2>
          <p className="text-sm text-center mb-6" style={{ color: "#6b8f74" }}>
            La verificación de correo todavía no está disponible. Tu cuenta ya
            funciona y puedes iniciar sesión con ella.
          </p>

          <button
            onClick={() => navigate("/login")}
            className="w-full rounded-xl py-3 text-sm font-semibold"
            style={{ background: "#2d5a3d", color: "#ffffff", border: "none", cursor: "pointer" }}
          >
            Ir a iniciar sesión
          </button>
        </div>
      </div>
    </div>
  );
}
