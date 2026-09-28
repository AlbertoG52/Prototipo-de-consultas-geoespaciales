import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  // host: true es necesario para que el contenedor exponga el servidor.
  // usePolling: en Docker Desktop sobre Windows los cambios hechos en el
  // anfitrión no generan eventos de archivo dentro del contenedor, así que sin
  // sondeo Vite sigue sirviendo la versión anterior. Cuesta algo de CPU.
  server: { host: true, port: 5173, watch: { usePolling: true, interval: 300 } },
});
