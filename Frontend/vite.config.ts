import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  // host: true expone el servidor desde el contenedor. usePolling: en Docker Desktop sobre Windows
  // los cambios del anfitrión no generan eventos de archivo dentro del contenedor; el sondeo los
  // detecta a cambio de algo de CPU.
  server: { host: true, port: 5173, watch: { usePolling: true, interval: 300 } },
});
