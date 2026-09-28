/**
 * Ficha completa de la especie.
 */
import { useParams, useNavigate } from "react-router";


/*
 * El mapa grande y los registros de ejemplo que venían del diseño no se
 * usan todavía: Se dejan aquí
 * comentados para que quien la implemente no los tenga que rehacer.
 *
 * function CostaRicaMapLarge() {
 *   return (
 *     <svg viewBox="0 0 500 280" className="w-full h-full" style={{ background: "#e8f0e8" }}>
 *       <path d="M80,140 Q120,90 180,80 Q240,70 300,90 Q350,100 380,125 Q410,145 395,175 Q380,205 340,220 Q280,235 210,232 Q140,228 105,205 Q70,180 80,140 Z" fill="#c8dfc0" stroke="#9ab89a" strokeWidth="2" />
 *       <ellipse cx="240" cy="148" rx="50" ry="32" fill="#b0d0a8" opacity="0.6" />
 *       <text x="220" y="125" fontSize="11" fill="#3d6040" fontFamily="Inter, sans-serif" fontWeight="500">Alajuela</text>
 *       <text x="215" y="148" fontSize="10" fill="#3d6040" fontFamily="Inter, sans-serif">Valle Central</text>
 *       <text x="300" y="175" fontSize="10" fill="#3d6040" fontFamily="Inter, sans-serif">Cartago</text>
 *       <text x="135" y="165" fontSize="10" fill="#3d6040" fontFamily="Inter, sans-serif">Puntarenas</text>
 *       {[[245,140],[258,132],[250,152],[236,136],[265,144],[242,160],[270,138]].map(([cx,cy],i) => (
 *         <circle key={i} cx={cx} cy={cy} r={5} fill="#5b4fcf" opacity={0.8} />
 *       ))}
 *       <circle cx="150" cy="250" r="7" fill="#5b4fcf" opacity="0.85" />
 *       <text x="164" y="254" fontSize="11" fill="#555" fontFamily="Inter, sans-serif">Registros GBIF (142)</text>
 *       <line x1="370" y1="255" x2="440" y2="255" stroke="#666" strokeWidth="2" />
 *       <line x1="370" y1="250" x2="370" y2="255" stroke="#666" strokeWidth="2" />
 *       <line x1="440" y1="250" x2="440" y2="255" stroke="#666" strokeWidth="2" />
 *       <text x="392" y="268" fontSize="10" fill="#666" fontFamily="Inter, sans-serif">50 km</text>
 *     </svg>
 *   );
 * }
 * 
 * const RECORDS = [
 *   { loc: "Alajuela, Valle Central", date: "12 mar 2024", lat: "10.0162° N", lon: "84.2133° W", elev: "1240 m", source: "GBIF" },
 *   { loc: "Cartago, Turrialba", date: "08 ene 2024", lat: "9.9014° N", lon: "83.6800° W", elev: "980 m", source: "GBIF" },
 *   { loc: "San José, Escazú", date: "22 nov 2023", lat: "9.9281° N", lon: "84.1363° W", elev: "1100 m", source: "GBIF" },
 *   { loc: "Heredia, Barva", date: "05 oct 2023", lat: "10.0726° N", lon: "84.1099° W", elev: "1380 m", source: "GBIF" },
 *   { loc: "Alajuela, Naranjo", date: "18 sep 2023", lat: "10.1011° N", lon: "84.3770° W", elev: "1150 m", source: "Manual MPCR" },
 * ];
 * 
 * 
 */

export function SpeciesPage() {
  const { name } = useParams();
  const navigate = useNavigate();
  const displayName = name ? decodeURIComponent(name) : "Guarianthe skinneri";


  return (
    <>
      {/* Header */}
      <div className="px-8 py-4 border-b shrink-0 flex items-center gap-3" style={{ background: "#ffffff", borderColor: "#dde8df" }}>
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-sm transition-all rounded-lg px-3 py-2" style={{ color: "#6b8f74", border: "none", background: "transparent", cursor: "pointer" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#f0f5f1"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M12 5l-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          Volver a consultas
        </button>
        <span style={{ color: "#dde8df" }}>|</span>
        <h1 className="text-base font-medium" style={{ color: "#1e3d2a" }}>Ficha completa de especie</h1>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ background: "#f7f8f5" }}>
        {/* Species hero */}
        <div className="px-8 py-8" style={{ background: "#2d5a3d" }}>
          <div className="max-w-4xl">
            <div className="text-xs font-medium tracking-widest mb-2" style={{ color: "#a8d4b0", letterSpacing: "0.15em" }}>ORCHIDACEAE</div>
            <h2 className="text-4xl font-bold mb-1" style={{ color: "#ffffff", fontFamily: "'Lora', serif" }}>Guaria Morada</h2>
            <p className="text-lg italic mb-4" style={{ color: "#c5e8cc" }}>{displayName || "Guarianthe skinneri"}</p>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "142 registros GBIF" },
                { label: "Flor nacional CR" },
                { label: "800–1600 msnm" },
                { label: "Especie nativa" },
              ].map((tag) => (
                <span key={tag.label} className="text-xs px-3 py-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.15)", color: "#e8f0eb" }}>{tag.label}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="px-8 py-6 max-w-4xl">
          <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 280px" }}>
              <div className="flex flex-col gap-5">
                <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                  <h3 className="font-semibold mb-3" style={{ color: "#1e3d2a" }}>Descripción general</h3>
                  <p className="text-sm leading-relaxed" style={{ color: "#374a3c" }}>
                    <em>Guarianthe skinneri</em>, conocida popularmente como <strong>Guaria Morada</strong>, es una orquídea epífita nativa de Costa Rica y Guatemala. Fue declarada flor nacional de Costa Rica en 1939. Sus flores, de tonalidades que van del morado pálido al rosado intenso, florecen típicamente entre enero y abril.
                  </p>
                  <p className="text-sm leading-relaxed mt-3" style={{ color: "#374a3c" }}>
                    La planta puede alcanzar hasta 60 cm de altura. Sus pseudobulbos son cilíndricos y alargados, con 2–3 hojas apicales coriáceas. Las raíces son gruesas y velamentosas, adaptadas para capturar humedad del aire en los bosques húmedos donde habita.
                  </p>
                </div>
                <div className="rounded-2xl p-6" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                  <h3 className="font-semibold mb-3" style={{ color: "#1e3d2a" }}>Fuentes consultadas</h3>
                  <div className="flex flex-col gap-2">
                    {[
                      { src: "GBIF", desc: "Global Biodiversity Information Facility — 142 registros de presencia", color: "#e8f0eb" },
                      { src: "Manual de Plantas de CR", desc: "Manual de Plantas de Costa Rica, Vol. III, 2003", color: "#e8f0eb" },
                    ].map((s) => (
                      <div key={s.src} className="flex items-start gap-3 p-3 rounded-xl" style={{ background: s.color }}>
                        <span className="text-xs px-2 py-1 rounded-full font-medium shrink-0 mt-0.5" style={{ background: "#2d5a3d", color: "#fff" }}>{s.src}</span>
                        <span className="text-xs" style={{ color: "#374a3c" }}>{s.desc}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-4">
                <div className="rounded-2xl p-5" style={{ background: "#ffffff", border: "1px solid #dde8df" }}>
                  <h3 className="font-semibold mb-3 text-sm" style={{ color: "#1e3d2a" }}>Datos clave</h3>
                  {[
                    ["Nombre común", "Guaria Morada"],
                    ["Nombre científico", "Guarianthe skinneri"],
                    ["Familia", "Orchidaceae"],
                    ["Elevación", "800 – 1600 msnm"],
                    ["Hábitat", "Bosque húmedo tropical"],
                    ["Floración", "Enero – Abril"],
                    ["Estado", "Especie nativa"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between py-2 text-xs" style={{ borderBottom: "1px solid #f0f5f1" }}>
                      <span style={{ color: "#8aab92" }}>{k}</span>
                      <span className="font-medium text-right" style={{ color: "#374a3c", maxWidth: "55%" }}>{v}</span>
                    </div>
                  ))}
                </div>
                <button className="w-full flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium" style={{ background: "#2d5a3d", color: "#fff", border: "none", cursor: "pointer" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  Exportar ficha
                </button>
              </div>
            </div>
        </div>
      </div>
    </>
  );
}
