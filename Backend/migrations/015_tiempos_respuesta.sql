-- RR_57: registro del tiempo de respuesta de cada consulta.
--
-- Una fila por cada POST /consultas, termine bien o mal: cuánto tardó desde
-- que llegó al backend hasta que la respuesta quedó lista, y cómo terminó.
-- La lee el equipo técnico en GET /admin/tiempos (solo supermoderador) para
-- encontrar las consultas lentas.
--
-- No guarda el texto de la consulta ni quién la hizo: el visitante anónimo no
-- deja rastro de lo que consultó (RR_00_11). De una cuenta registrada se
-- guarda el id de la consulta, que ya está en 'consultas'; si esa consulta se
-- borra, el tiempo se conserva sin el enlace.
CREATE TABLE IF NOT EXISTS tiempos_respuesta (
    id            SERIAL PRIMARY KEY,
    registrada_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    duracion_ms   INTEGER     NOT NULL CHECK (duracion_ms >= 0),
    -- resuelta, ambigua, sin_coincidencias, tiempo_agotado, limite_alcanzado,
    -- rechazada o error (dominio.ResultadoConsulta).
    resultado     VARCHAR(30) NOT NULL,
    tipo_sesion   VARCHAR(20) NOT NULL,  -- usuario o anonimo
    especie_id    VARCHAR(100),          -- la especie respondida, si la hubo
    consulta_id   INTEGER REFERENCES consultas(id) ON DELETE SET NULL
);

-- Para listar las más recientes y para buscar las lentas.
CREATE INDEX IF NOT EXISTS idx_tiempos_respuesta_fecha ON tiempos_respuesta (registrada_en DESC);
CREATE INDEX IF NOT EXISTS idx_tiempos_respuesta_duracion ON tiempos_respuesta (duracion_ms DESC);
