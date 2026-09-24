/**
 * Rutas de la aplicación.
 *
 * Root va primero y no está protegida: cualquier persona entra directo al
 * agente, tenga cuenta o no (RR_00_11). 
 */
import { createBrowserRouter } from "react-router";

import { AdminPage } from "./pages/AdminPage";
import { ChatPage } from "./pages/ChatPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RegisterPage } from "./pages/RegisterPage";
import { Root } from "./pages/Root";
import { SpeciesPage } from "./pages/SpeciesPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: ChatPage },
      { path: "species/:name", Component: SpeciesPage },
      { path: "admin", Component: AdminPage },
      { path: "profile", Component: ProfilePage },
    ],
  },
  { path: "/login", Component: LoginPage },
  { path: "/register", Component: RegisterPage },

  // RR_00_06 y RR_00_07. 
  { path: "/forgot-password", Component: ForgotPasswordPage },
  { path: "/verify-email", Component: VerifyEmailPage },
]);
