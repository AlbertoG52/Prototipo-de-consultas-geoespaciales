import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [estado, setEstado] = useState<string>("consultando...");

  useEffect(() => {
    fetch(`${API}/db-check`)
      .then((r) => r.json())
      .then((d) => setEstado(`API y BD OK — roles en la base: ${d.roles_en_bd}`))
      .catch(() => setEstado("No se pudo conectar con la API"));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>Prototipo de consultas geoespaciales</h1>
      <p>Estado de la conexión: {estado}</p>
    </main>
  );
}
