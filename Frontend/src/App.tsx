import { RouterProvider } from "react-router";

import { AuthProvider } from "./context/AuthContext";
import { ConsultasProvider } from "./context/ConsultasContext";
import { router } from "./routes";

export default function App() {
  return (
    <AuthProvider>
      <ConsultasProvider>
        <RouterProvider router={router} />
      </ConsultasProvider>
    </AuthProvider>
  );
}
