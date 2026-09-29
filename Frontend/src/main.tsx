import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./index.css";
import { aplicarFuente, leerFuente } from "./utils/apariencia";

// La fuente se aplica aquí; el tema ya lo aplicó index.html al cargar.
aplicarFuente(leerFuente());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
