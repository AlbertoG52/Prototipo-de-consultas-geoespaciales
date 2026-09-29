/**
 * Preferencias de apariencia: modo oscuro y tipo de letra.
 *
 */

export type Tema = "claro" | "oscuro";

export type Fuente = "inter" | "lora" | "atkinson" | "sistema";

export const FUENTES: { id: Fuente; nombre: string; descripcion: string; css: string }[] = [
  {
    id: "inter",
    nombre: "Inter",
    descripcion: "La predeterminada.",
    css: "'Inter', sans-serif",
  },
  {
    id: "lora",
    nombre: "Lora",
    descripcion: "Con serifa, más tradicional.",
    css: "'Lora', serif",
  },
  {
    id: "atkinson",
    nombre: "Atkinson Hyperlegible",
    descripcion: "Diseñada para leerse con baja visión.",
    css: "'Atkinson Hyperlegible', sans-serif",
  },
  {
    id: "sistema",
    nombre: "La del sistema",
    descripcion: "La que usa tu computadora o celular.",
    css: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  },
];

const CLAVE_TEMA = "apariencia.tema";
const CLAVE_FUENTE = "apariencia.fuente";

function leer(clave: string): string | null {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardar(clave: string, valor: string) {
  try {
    localStorage.setItem(clave, valor);
  } catch {
    /* sin almacenamiento: se aplica solo mientras la página esté abierta */
  }
}

export function leerTema(): Tema {
  return leer(CLAVE_TEMA) === "oscuro" ? "oscuro" : "claro";
}

export function leerFuente(): Fuente {
  const valor = leer(CLAVE_FUENTE);
  return FUENTES.some((f) => f.id === valor) ? (valor as Fuente) : "inter";
}

export function aplicarTema(tema: Tema) {
  document.documentElement.dataset.tema = tema;
  guardar(CLAVE_TEMA, tema);
}

export function aplicarFuente(fuente: Fuente) {
  const opcion = FUENTES.find((f) => f.id === fuente) ?? FUENTES[0];
  document.documentElement.style.setProperty("--fuente-app", opcion.css);
  guardar(CLAVE_FUENTE, opcion.id);
}
