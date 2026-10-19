/**
 * Mapa de distribución de CR-BioLM y controles de los registros — RR_46,
 * RR_48, RR_52, RR_53, RR_12 y RR_19.
 *
 * Todos los mapas vienen de CR-BioLM (PNG). Si la respuesta no trae mapa, no
 * se muestra ninguno. El detalle de un registro (RR_12, en una ventana) y el
 * filtro por elevación (RR_19) trabajan sobre la tabla de registros, porque en
 * una imagen no se puede seleccionar ni ocultar puntos.
 */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { ChevronLeft, ChevronRight, Download, List, Maximize2, RotateCcw, X, ZoomIn, ZoomOut } from "lucide-react";
import * as api from "../services/api";
import type { MapaEspecie, RegistroPresencia } from "../types";
import { RANGO_VACIO, type RangoElevacion } from "../utils/elevacion";
import { ETIQUETAS_REGISTRO, formatearCoordenadas, SIN_DATO, textoRegistros } from "../config/textos";
import { LEYENDA_MAPA, NOTA_REGIONES } from "../config/leyendaMapa";

type EstadoImagen =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; url: string };

/**
 * Descarga el PNG del mapa con la sesión y lo convierte en una URL local
 * (blob:). La URL se libera al desmontar el componente o al cambiar de mapa.
 */
function useImagenMapa(ruta: string): EstadoImagen {
  const [estado, setEstado] = useState<EstadoImagen>({ tipo: "cargando" });

  useEffect(() => {
    let vigente = true;
    let url: string | null = null;
    setEstado({ tipo: "cargando" });
    api
      .obtenerImagenMapa(ruta)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        // Si el componente ya se desmontó, la URL no llega a usarse.
        if (vigente) setEstado({ tipo: "lista", url });
        else URL.revokeObjectURL(url);
      })
      .catch((err) => {
        if (!vigente) return;
        const mensaje =
          err instanceof api.ErrorApi && err.status === 404
            ? "CR-BioLM no tiene un mapa disponible para esta especie."
            : "No se pudo cargar el mapa. Intenta de nuevo más tarde.";
        setEstado({ tipo: "error", mensaje });
      });
    return () => {
      vigente = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [ruta]);

  return estado;
}

/**
 * RR_48 criterio 1 — qué significa cada símbolo del mapa (config/leyendaMapa.ts).
 *
 * Va fuera de la imagen: en el visor queda fija sobre el mapa aunque se haga
 * zoom o se arrastre (criterio 3), y debajo del mapa pequeño se despliega.
 */
function LeyendaMapa({ puntos, oscura = false }: { puntos: number; oscura?: boolean }) {
  const colorTexto = oscura ? "#e5e7eb" : "var(--color-texto-cuerpo)";
  const colorNota = oscura ? "#9ca3af" : "var(--color-texto-tenue)";
  return (
    <div className="flex flex-col gap-1.5 text-xs">
      <ul className="flex flex-col gap-1 m-0 p-0 list-none">
        {LEYENDA_MAPA.map((s) => (
          <li key={s.etiqueta} className="flex items-start gap-2" style={{ color: colorTexto }}>
            <span
              aria-hidden="true"
              className="inline-block rounded-sm shrink-0 mt-0.5"
              style={{
                width: 14,
                height: 10,
                background: s.contorno
                  ? "transparent"
                  : s.rayado
                    ? `repeating-linear-gradient(45deg, ${s.color} 0 2px, transparent 2px 4px)`
                    : s.color,
                border: s.contorno
                  ? `1.5px ${s.discontinuo ? "dashed" : "solid"} ${oscura ? s.color : (s.contornoEnClaro ?? s.color)}`
                  : `1px solid ${s.borde ?? s.color}`,
              }}
            />
            <span>
              {s.etiqueta}
              {s.registros && puntos > 0 && ` (${puntos})`}
            </span>
          </li>
        ))}
      </ul>
      <p className="m-0" style={{ color: colorNota }}>
        {NOTA_REGIONES}
      </p>
    </div>
  );
}

/**
 * RR_46 — mapa de distribución generado por CR-BioLM.
 *
 * - Criterio 1: solo se monta cuando la respuesta trae `mapa` (hay datos
 *   geoespaciales); quien lo usa no lo muestra si `mapa` es null (RR_53).
 * - Criterio 2: la imagen es la de CR-BioLM, con las zonas de distribución.
 * - Criterio 3: el texto alternativo y el título nombran la especie.
 *
 * RR_15: "Descargar mapa" baja este mismo PNG.
 * RR_59: debajo del mapa se indica cuántos registros de GBIF tiene dibujados.
 * RR_48: la leyenda se despliega debajo del mapa y en el visor queda fija
 * sobre el mapa al hacer zoom.
 *
 * Al hacer clic en el mapa, o en "Pantalla completa", se abre en grande
 * (VisorMapa). Se usa en el chat (TarjetaRespuesta) y en la ficha (SpeciesPage).
 */
export function MapaCRBioLM({
  mapa,
  especie,
  nombreArchivo,
}: {
  mapa: MapaEspecie;
  /** Nombre científico de la especie del mapa. */
  especie: string;
  /** Nombre del archivo al descargar el mapa (RR_15). */
  nombreArchivo: string;
}) {
  const imagen = useImagenMapa(mapa.url);
  const [ampliado, setAmpliado] = useState(false);
  const textoAlternativo = `Mapa de distribución de ${especie} en Costa Rica, generado por CR-BioLM.`;

  return (
    <figure className="m-0">
      {imagen.tipo === "lista" && (
        <div className="flex justify-end gap-1 mb-1">
          <button
            onClick={() => setAmpliado(true)}
            className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs transition-all"
            style={{ color: "var(--color-texto-tenue)", background: "transparent", border: "none", cursor: "pointer" }}
          >
            <Maximize2 size={12} />
            Pantalla completa
          </button>
          <a
            href={imagen.url}
            download={nombreArchivo}
            className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs transition-all"
            style={{ color: "var(--color-texto-tenue)", textDecoration: "none" }}
          >
            <Download size={12} />
            Descargar mapa
          </a>
        </div>
      )}
      <div
        className="rounded-xl overflow-hidden flex items-center justify-center"
        style={{ border: "1px solid var(--color-borde)", background: "var(--color-superficie-suave)", minHeight: 170 }}
      >
        {imagen.tipo === "cargando" && (
          <p role="status" className="text-xs" style={{ color: "var(--color-texto-tenue)" }}>
            Cargando el mapa…
          </p>
        )}
        {imagen.tipo === "error" && (
          <p role="alert" className="text-xs px-4 text-center" style={{ color: "var(--color-texto-secundario)" }}>
            {imagen.mensaje}
          </p>
        )}
        {imagen.tipo === "lista" && (
          <button
            onClick={() => setAmpliado(true)}
            aria-label={`Ver el mapa de ${especie} en pantalla completa`}
            title="Ver en pantalla completa"
            className="w-full block p-0"
            style={{ border: "none", background: "transparent", cursor: "zoom-in" }}
          >
            <img src={imagen.url} alt={textoAlternativo} className="w-full h-auto block" />
          </button>
        )}
      </div>
      {ampliado && imagen.tipo === "lista" && (
        <VisorMapa
          url={imagen.url}
          especie={especie}
          puntos={mapa.puntos}
          textoAlternativo={textoAlternativo}
          nombreArchivo={nombreArchivo}
          onCerrar={() => setAmpliado(false)}
        />
      )}
      <figcaption className="mt-1.5 text-xs flex flex-col gap-0.5">
        {/* RR_59 criterio 2: la cantidad de registros junto al mapa. */}
        {mapa.puntos > 0 && (
          <span style={{ color: "var(--color-texto-secundario)" }}>
            {textoRegistros(mapa.puntos)} de presencia de GBIF en el mapa
          </span>
        )}
        {/* Aviso de CR-BioLM sobre el mapa, si lo hay. */}
        {mapa.advertencia && <span style={{ color: "var(--color-aviso-texto)" }}>{mapa.advertencia}</span>}
      </figcaption>
      {imagen.tipo === "lista" && (
        <details className="mt-1.5">
          <summary className="text-xs cursor-pointer select-none" style={{ color: "var(--color-texto-secundario)" }}>
            Leyenda del mapa
          </summary>
          <div className="mt-2 rounded-xl px-3 py-2.5" style={{ background: "var(--color-superficie-suave)" }}>
            <LeyendaMapa puntos={mapa.puntos} />
          </div>
        </details>
      )}
    </figure>
  );
}

// Zoom del visor: de 1× (el mapa entero) a ZOOM_MAXIMO×. Es un PNG, así que
// más allá de unas 3–4× solo se agrandan los píxeles.
const ZOOM_MAXIMO = 4;
const PASO_ZOOM = 1.5;

type Punto = { x: number; y: number };

function limitar(valor: number, minimo: number, maximo: number): number {
  return Math.min(Math.max(valor, minimo), maximo);
}

/**
 * El mapa en grande, sobre un fondo oscuro que cubre la pantalla.
 *
 * Zoom: rueda del mouse (hacia donde está el cursor), doble clic, botones
 * + / − / restablecer, teclas + − 0, y pellizcar en el teléfono. Con zoom, el
 * mapa se mueve arrastrándolo, sin salirse de la vista.
 *
 * Se cierra con la X, con Escape o con un clic fuera del mapa. Mientras está
 * abierto la página de atrás no se desplaza, y al cerrarlo el foco vuelve a
 * donde estaba.
 */
function VisorMapa({
  url,
  especie,
  puntos,
  textoAlternativo,
  nombreArchivo,
  onCerrar,
}: {
  url: string;
  especie: string;
  /** Registros de GBIF dibujados en el mapa, para la leyenda (RR_48). */
  puntos: number;
  textoAlternativo: string;
  nombreArchivo: string;
  onCerrar: () => void;
}) {
  const cerrarRef = useRef<HTMLButtonElement>(null);
  const zonaRef = useRef<HTMLDivElement>(null);
  const imagenRef = useRef<HTMLImageElement>(null);
  const [vista, setVista] = useState({ escala: 1, x: 0, y: 0 });
  // Copia inmediata de `vista`: varios eventos seguidos (rueda, pellizco)
  // pueden llegar antes de que React vuelva a dibujar.
  const vistaRef = useRef(vista);
  const [arrastrando, setArrastrando] = useState(false);
  // RR_48: la leyenda empieza visible y se puede ocultar para ver todo el mapa.
  const [conLeyenda, setConLeyenda] = useState(true);
  // Punteros apoyados (mouse o dedos), dónde empezó el gesto y si hubo
  // movimiento, para no confundir el final de un arrastre con un clic que cierra.
  const punteros = useRef(new Map<number, Punto>());
  const empezoFuera = useRef(false);
  const seMovio = useRef(false);
  const escala = vista.escala;

  const aplicar = (nueva: { escala: number; x: number; y: number }) => {
    vistaRef.current = nueva;
    setVista(nueva);
  };

  // La última onCerrar, para que el efecto corra solo al abrir y al cerrar.
  const onCerrarRef = useRef(onCerrar);
  useEffect(() => {
    onCerrarRef.current = onCerrar;
  }, [onCerrar]);

  /** Mantiene el mapa dentro de la vista: sin zoom queda centrado. */
  const ajustar = (nuevaEscala: number, punto: Punto): Punto => {
    const imagen = imagenRef.current;
    if (!imagen || nuevaEscala <= 1) return { x: 0, y: 0 };
    const maxX = ((nuevaEscala - 1) * imagen.offsetWidth) / 2;
    const maxY = ((nuevaEscala - 1) * imagen.offsetHeight) / 2;
    return { x: limitar(punto.x, -maxX, maxX), y: limitar(punto.y, -maxY, maxY) };
  };

  /** Multiplica el zoom por `factor` dejando quieto el punto `foco` de la pantalla (o el centro). */
  const hacerZoom = (factor: number, foco?: Punto) => {
    const zona = zonaRef.current;
    if (!zona) return;
    const actual = vistaRef.current;
    const destino = limitar(actual.escala * factor, 1, ZOOM_MAXIMO);
    const real = destino / actual.escala;
    const caja = zona.getBoundingClientRect();
    const centro = { x: caja.left + caja.width / 2, y: caja.top + caja.height / 2 };
    const relativo = foco ? { x: foco.x - centro.x, y: foco.y - centro.y } : { x: 0, y: 0 };
    const punto = ajustar(destino, {
      x: relativo.x - real * (relativo.x - actual.x),
      y: relativo.y - real * (relativo.y - actual.y),
    });
    aplicar({ escala: destino, ...punto });
  };

  const restablecer = () => aplicar({ escala: 1, x: 0, y: 0 });

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    const desplazamientoPagina = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cerrarRef.current?.focus();
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCerrarRef.current();
      else teclasZoomRef.current(e);
    };
    window.addEventListener("keydown", alTeclear);
    return () => {
      window.removeEventListener("keydown", alTeclear);
      document.body.style.overflow = desplazamientoPagina;
      anterior?.focus();
    };
  }, []);

  // Teclas + − 0 (el efecto de arriba las recibe en toda la ventana).
  const teclasZoomRef = useRef<(e: KeyboardEvent) => void>(() => undefined);
  useEffect(() => {
    teclasZoomRef.current = (e: KeyboardEvent) => {
      if (e.key === "+" || e.key === "=") hacerZoom(PASO_ZOOM);
      else if (e.key === "-") hacerZoom(1 / PASO_ZOOM);
      else if (e.key === "0") restablecer();
    };
  });

  const alApoyar = (e: React.PointerEvent) => {
    punteros.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (punteros.current.size === 1) {
      seMovio.current = false;
      empezoFuera.current = e.target === e.currentTarget;
    }
    if (punteros.current.size === 1 && vistaRef.current.escala > 1) setArrastrando(true);
  };

  const alMover = (e: React.PointerEvent) => {
    const antes = punteros.current.get(e.pointerId);
    if (!antes) return;
    const ahora = { x: e.clientX, y: e.clientY };
    if (Math.abs(ahora.x - antes.x) + Math.abs(ahora.y - antes.y) > 2) {
      seMovio.current = true;
      // Desde que hay arrastre, el gesto sigue aunque el puntero salga del mapa.
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.setPointerCapture(e.pointerId);
    }

    if (punteros.current.size === 2) {
      // Pellizco: la escala cambia en proporción a la distancia entre los dedos.
      const [otroId] = [...punteros.current.keys()].filter((id) => id !== e.pointerId);
      const otro = punteros.current.get(otroId)!;
      const distanciaAntes = Math.hypot(antes.x - otro.x, antes.y - otro.y);
      const distanciaAhora = Math.hypot(ahora.x - otro.x, ahora.y - otro.y);
      if (distanciaAntes > 0) {
        const medio = { x: (ahora.x + otro.x) / 2, y: (ahora.y + otro.y) / 2 };
        hacerZoom(distanciaAhora / distanciaAntes, medio);
      }
    } else if (vistaRef.current.escala > 1) {
      const actual = vistaRef.current;
      const punto = ajustar(actual.escala, { x: actual.x + ahora.x - antes.x, y: actual.y + ahora.y - antes.y });
      aplicar({ escala: actual.escala, ...punto });
    }
    punteros.current.set(e.pointerId, ahora);
  };

  const alSoltar = (e: React.PointerEvent) => {
    punteros.current.delete(e.pointerId);
    if (punteros.current.size === 0) setArrastrando(false);
  };

  // Un clic fuera del mapa (que empezó fuera y sin arrastrar) cierra el visor.
  const alHacerClicEnZona = () => {
    if (empezoFuera.current && !seMovio.current) onCerrar();
  };

  const estiloBoton = {
    color: "#fff",
    background: "rgba(255, 255, 255, 0.12)",
    border: "none",
    cursor: "pointer",
    textDecoration: "none",
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Mapa de distribución de ${especie}`}
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: "rgba(0, 0, 0, 0.85)" }}
    >
      <div className="flex items-center gap-2 px-4 py-3 shrink-0">
        <span className="flex-1 min-w-0 truncate text-sm" style={{ color: "#fff" }}>
          Mapa de distribución de <em>{especie}</em>
        </span>
        <div className="flex items-center gap-1" role="group" aria-label="Zoom del mapa">
          <button
            onClick={() => hacerZoom(1 / PASO_ZOOM)}
            disabled={escala <= 1}
            aria-label="Alejar"
            title="Alejar (−)"
            className="p-1.5 rounded-lg disabled:opacity-40"
            style={estiloBoton}
          >
            <ZoomOut size={16} />
          </button>
          <span className="text-xs w-10 text-center tabular-nums" style={{ color: "#fff" }} aria-live="polite">
            {Math.round(escala * 100)}%
          </span>
          <button
            onClick={() => hacerZoom(PASO_ZOOM)}
            disabled={escala >= ZOOM_MAXIMO}
            aria-label="Acercar"
            title="Acercar (+)"
            className="p-1.5 rounded-lg disabled:opacity-40"
            style={estiloBoton}
          >
            <ZoomIn size={16} />
          </button>
          <button
            onClick={restablecer}
            disabled={escala === 1}
            aria-label="Ver el mapa completo"
            title="Ver el mapa completo (0)"
            className="p-1.5 rounded-lg disabled:opacity-40"
            style={estiloBoton}
          >
            <RotateCcw size={16} />
          </button>
        </div>
        <button
          onClick={() => setConLeyenda((v) => !v)}
          aria-pressed={conLeyenda}
          aria-label={conLeyenda ? "Ocultar la leyenda" : "Mostrar la leyenda"}
          title={conLeyenda ? "Ocultar la leyenda" : "Mostrar la leyenda"}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
          style={{ ...estiloBoton, background: conLeyenda ? "rgba(255, 255, 255, 0.24)" : estiloBoton.background }}
        >
          <List size={14} />
          <span className="hidden sm:inline">Leyenda</span>
        </button>
        <a
          href={url}
          download={nombreArchivo}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
          style={estiloBoton}
        >
          <Download size={14} />
          <span className="hidden sm:inline">Descargar mapa</span>
        </a>
        <button
          ref={cerrarRef}
          onClick={onCerrar}
          aria-label="Cerrar el mapa"
          className="p-1.5 rounded-lg"
          style={estiloBoton}
        >
          <X size={18} />
        </button>
      </div>
      <div
        ref={zonaRef}
        className="relative flex-1 min-h-0 flex items-center justify-center p-4 pt-0 overflow-hidden select-none"
        style={{ touchAction: "none" }}
        onClick={alHacerClicEnZona}
        onWheel={(e) => hacerZoom(e.deltaY < 0 ? 1.2 : 1 / 1.2, { x: e.clientX, y: e.clientY })}
        onPointerDown={alApoyar}
        onPointerMove={alMover}
        onPointerUp={alSoltar}
        onPointerCancel={alSoltar}
      >
        <img
          ref={imagenRef}
          src={url}
          alt={textoAlternativo}
          draggable={false}
          className="max-w-full max-h-full object-contain rounded-lg"
          onDoubleClick={(e) => (escala > 1 ? restablecer() : hacerZoom(2, { x: e.clientX, y: e.clientY }))}
          style={{
            background: "#fff",
            transform: `translate(${vista.x}px, ${vista.y}px) scale(${escala})`,
            transition: arrastrando ? "none" : "transform 0.12s ease-out",
            cursor: escala > 1 ? (arrastrando ? "grabbing" : "grab") : "zoom-in",
          }}
        />
        {/* RR_48 criterio 3: fuera de la imagen, así no se mueve ni se corta con el zoom. */}
        {conLeyenda && (
          <div
            role="region"
            aria-label="Leyenda del mapa"
            className="absolute left-4 bottom-4 max-w-[min(20rem,calc(100%-2rem))] max-h-[60%] overflow-y-auto rounded-xl px-3 py-2.5"
            style={{ background: "rgba(17, 24, 39, 0.9)", border: "1px solid #374151" }}
            onPointerDown={(e) => e.stopPropagation()}
            onWheel={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-xs font-semibold mb-1.5" style={{ color: "#fff" }}>
              Leyenda
            </div>
            <LeyendaMapa puntos={puntos} oscura />
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/**
 * RR_12 — detalle del punto seleccionado.
 *
 * Se abre en una ventana al hacer clic en una fila de la tabla de registros,
 * así no hay que bajar hasta el final de una lista larga para verlo. Se cierra
 * con la X, con Escape o con un clic fuera. Con `onAnterior` y `onSiguiente`
 * se recorren los registros visibles sin cerrarla (también con ← y →).
 */
export function DetallePunto({
  registro,
  onCerrar,
  posicion,
  onAnterior,
  onSiguiente,
}: {
  registro: RegistroPresencia;
  onCerrar: () => void;
  /** Lugar del registro entre los visibles (1 = el primero). */
  posicion?: { actual: number; total: number };
  onAnterior?: () => void;
  onSiguiente?: () => void;
}) {
  const cerrarRef = useRef<HTMLButtonElement>(null);
  // Las últimas funciones, para que el efecto corra solo al abrir y al cerrar.
  const acciones = useRef({ onCerrar, onAnterior, onSiguiente });
  useEffect(() => {
    acciones.current = { onCerrar, onAnterior, onSiguiente };
  });

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    cerrarRef.current?.focus();
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") acciones.current.onCerrar();
      else if (e.key === "ArrowLeft") acciones.current.onAnterior?.();
      else if (e.key === "ArrowRight") acciones.current.onSiguiente?.();
    };
    window.addEventListener("keydown", alTeclear);
    return () => {
      window.removeEventListener("keydown", alTeclear);
      anterior?.focus();
    };
  }, []);

  const filas: [string, string][] = [
    [ETIQUETAS_REGISTRO.localidad, registro.localidad],
    [ETIQUETAS_REGISTRO.fechaDelRegistro, registro.fecha],
    [ETIQUETAS_REGISTRO.coordenadas, formatearCoordenadas(registro)],
    [ETIQUETAS_REGISTRO.elevacion, registro.elevacion_m !== null ? `${registro.elevacion_m} msnm` : SIN_DATO],
    [ETIQUETAS_REGISTRO.fuente, registro.fuente],
  ];

  const estiloNavegar = {
    border: "1px solid var(--color-borde-fuerte)",
    background: "transparent",
    color: "var(--color-texto-cuerpo)",
    cursor: "pointer",
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0, 0, 0, 0.5)" }}
      onClick={onCerrar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Detalle del registro en ${registro.localidad}`}
        className="w-full max-w-sm rounded-2xl px-5 py-4 text-sm shadow-xl"
        style={{ background: "var(--color-superficie)", border: "1px solid var(--color-borde-fuerte)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="flex items-center gap-1.5 font-semibold" style={{ color: "var(--color-texto)" }}>
            <span className="inline-block rounded-full" style={{ width: 8, height: 8, background: "var(--color-mapa-activo)" }} />
            Detalle del registro
          </span>
          <button
            ref={cerrarRef}
            onClick={onCerrar}
            aria-label="Cerrar detalle"
            className="p-1.5 rounded-md"
            style={{ border: "none", background: "transparent", color: "var(--color-texto-secundario)", cursor: "pointer" }}
          >
            <X size={16} />
          </button>
        </div>
        <dl className="grid gap-x-4 gap-y-1.5 text-xs" style={{ gridTemplateColumns: "auto 1fr" }}>
          {filas.map(([k, v]) => (
            <div key={k} className="contents">
              <dt style={{ color: "var(--color-texto-tenue)" }}>{k}</dt>
              <dd className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>
                {v}
              </dd>
            </div>
          ))}
        </dl>
        {posicion && (onAnterior || onSiguiente) && (
          <div className="flex items-center justify-between gap-2 mt-4 pt-3" style={{ borderTop: "1px solid var(--color-borde)" }}>
            <button
              onClick={onAnterior}
              disabled={!onAnterior}
              aria-label="Registro anterior"
              title="Registro anterior (←)"
              className="p-1.5 rounded-lg disabled:opacity-40"
              style={estiloNavegar}
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs" style={{ color: "var(--color-texto-secundario)" }} aria-live="polite">
              Registro {posicion.actual} de {posicion.total}
            </span>
            <button
              onClick={onSiguiente}
              disabled={!onSiguiente}
              aria-label="Registro siguiente"
              title="Registro siguiente (→)"
              className="p-1.5 rounded-lg disabled:opacity-40"
              style={estiloNavegar}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/** RR_19 — campos para definir el rango de elevación y quitar el filtro. */
export function FiltroElevacion({
  rango,
  onCambiar,
  visibles,
  total,
  activo,
  error,
}: {
  rango: RangoElevacion;
  onCambiar: (rango: RangoElevacion) => void;
  visibles: number;
  total: number;
  activo: boolean;
  error: string | null;
}) {
  const hayTexto = rango.min !== "" || rango.max !== "";
  const estiloCampo = {
    width: 84,
    border: `1.5px solid ${error ? "var(--color-error-borde)" : "var(--color-borde-fuerte)"}`,
    background: "var(--color-fondo)",
    color: "var(--color-texto)",
  };

  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 flex-wrap text-xs" role="group" aria-label="Filtrar por elevación">
        <span className="font-medium" style={{ color: "var(--color-texto-cuerpo)" }}>
          Elevación (msnm):
        </span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          placeholder="Mínima"
          aria-label="Elevación mínima en metros"
          value={rango.min}
          onChange={(e) => onCambiar({ ...rango, min: e.target.value })}
          className="rounded-lg px-2 py-1 outline-none"
          style={estiloCampo}
        />
        <span style={{ color: "var(--color-texto-tenue)" }}>a</span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          placeholder="Máxima"
          aria-label="Elevación máxima en metros"
          value={rango.max}
          onChange={(e) => onCambiar({ ...rango, max: e.target.value })}
          className="rounded-lg px-2 py-1 outline-none"
          style={estiloCampo}
        />
        {/* RR_19 criterio 3: volver a ver todos los puntos. */}
        {hayTexto && (
          <button
            onClick={() => onCambiar(RANGO_VACIO)}
            className="px-2 py-1 rounded-lg font-medium"
            style={{ border: "1px solid var(--color-borde-fuerte)", background: "transparent", color: "var(--color-texto-marca)", cursor: "pointer" }}
          >
            Quitar filtro
          </button>
        )}
        {activo && (
          <span aria-live="polite" style={{ color: "var(--color-texto-secundario)" }}>
            Mostrando {visibles} de {total} registros
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className="text-xs mt-1" style={{ color: "var(--color-error-texto)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
