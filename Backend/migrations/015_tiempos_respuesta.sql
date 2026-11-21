-- Tiempo de respuesta de cada consulta.
--
-- Una fila por cada POST /consultas, termine bien o mal: cuánto tardó y cómo terminó. Se
-- consulta en GET /admin/tiempos. No guarda el texto ni quién consultó; de una cuenta
-- guarda el id de la consulta.
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
