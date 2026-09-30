/**
 * Rutas de la aplicación.
 *
 * Root va primero y no está protegida: cualquier persona entra directo al
 * agente, tenga cuenta o no (RR_00_11).
 */
import type { ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router";

import { useAuth } from "./context/AuthContext";
import type { Usuario } from "./types";
import { AdminPage } from "./pages/AdminPage";
import { ChatPage } from "./pages/ChatPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { Root } from "./pages/Root";
import { SpeciesPage } from "./pages/SpeciesPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

/**
 * Muestra la vista solo a los roles indicados; al resto lo devuelve al agente
 * — RR_00_10.
 *
 * Es solo presentación: evita mostrar una pantalla cuyas peticiones igual
 * fallarían. La seguridad real está en el backend (requiere_rol), que responde
 * 403 aunque alguien se salte esta comprobación desde el navegador.
 *
 * Mientras la sesión carga no se decide nada; de lo contrario, quien entra
 * directo a la URL sería redirigido antes de saber quién es.
 */
function RequiereRol({ roles, children }: { roles: Usuario["rol"][]; children: ReactNode }) {
  const { sesion, cargando } = useAuth();
  if (cargando || !sesion) return null;

  const rol = sesion.usuario?.rol;
  if (!rol || !roles.includes(rol)) return <Navigate to="/" replace />;

  return children;
}

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: ChatPage },
      { path: "species/:name", Component: SpeciesPage },
      {
        path: "admin",
        element: (
          <RequiereRol roles={["supermoderador"]}>
            <AdminPage />
          </RequiereRol>
        ),
      },
      { path: "profile", Component: ProfilePage },
    ],
  },
  { path: "/login", Component: LoginPage },
  { path: "/register", Component: RegisterPage },

  // RR_00_06 y RR_00_07. /verify-email también recibe el enlace del correo (?token=).
  { path: "/forgot-password", Component: ForgotPasswordPage },
  { path: "/reset-password", Component: ResetPasswordPage },
  { path: "/verify-email", Component: VerifyEmailPage },
]);
