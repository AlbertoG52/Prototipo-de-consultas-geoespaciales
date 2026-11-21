/**
 * Rutas de la aplicación.
 *
 * Root no está protegida: cualquier persona entra directo al agente, tenga cuenta o no.
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
 * Muestra la vista solo a los roles indicados; al resto lo devuelve al agente.
 *
 * Es solo presentación: la seguridad está en el backend (requiere_rol), que responde 403. Mientras
 * la sesión carga no se decide nada, para no redirigir antes de saber quién es.
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

  // Recuperación de contraseña y verificación de correo. /verify-email recibe el enlace del correo
  // (?token=).
  { path: "/forgot-password", Component: ForgotPasswordPage },
  { path: "/reset-password", Component: ResetPasswordPage },
  { path: "/verify-email", Component: VerifyEmailPage },
]);
