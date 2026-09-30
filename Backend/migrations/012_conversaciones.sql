-- RR_09: el historial pasa de ser una lista de consultas sueltas a una lista
-- de conversaciones, como en un chat. Cada consulta pertenece a una.
--
-- Además se guardan las consultas de los tres estados, no solo las resueltas,
-- para poder reconstruir la conversación completa al reabrirla:
--
--   estado             se guarda  descuenta del límite  al reabrir se ve
--   resuelta           sí         sí                    la respuesta
--   ambigua            sí         no                    las opciones, que se pueden elegir
--   sin_coincidencias  sí         no                    el aviso
--
-- Una consulta ambigua queda pendiente. Cuando el usuario elige la especie,
-- aunque sea otro día, esa misma fila pasa a 'resuelta' y recién ahí cuenta.

CREATE TABLE IF NOT EXISTS conversaciones (
    id             SERIAL PRIMARY KEY,
    usuario_id     INTEGER      NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo         VARCHAR(120) NOT NULL,
    creada_en      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actualizada_en TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversaciones_usuario
    ON conversaciones (usuario_id, actualizada_en DESC);

ALTER TABLE consultas
    ADD COLUMN IF NOT EXISTS conversacion_id INTEGER REFERENCES conversaciones(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS estado          VARCHAR(20) NOT NULL DEFAULT 'resuelta',
    -- Las especies que se le ofrecieron al usuario (solo en 'ambigua').
    ADD COLUMN IF NOT EXISTS candidatos      JSONB,
    -- El texto que se le mostró en lugar de una respuesta ('ambigua' y 'sin_coincidencias').
    ADD COLUMN IF NOT EXISTS mensaje         TEXT,
    -- Cuándo se resolvió. Es la fecha con la que se cuenta el límite diario:
    -- una ambigua de ayer que se resuelve hoy cuenta hoy.
    ADD COLUMN IF NOT EXISTS resuelta_en     TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'consultas_estado_valido'
    ) THEN
        ALTER TABLE consultas ADD CONSTRAINT consultas_estado_valido
            CHECK (estado IN ('resuelta', 'ambigua', 'sin_coincidencias'));
    END IF;
END $$;

-- Hasta ahora solo se guardaban consultas resueltas: cada una pasa a ser su
-- propia conversación, con la consulta como título, para no perder el
-- historial que ya existe.
DO $$
DECLARE
    fila  RECORD;
    nueva INTEGER;
BEGIN
    FOR fila IN
        SELECT id, usuario_id, texto, realizada_en
        FROM consultas
        WHERE conversacion_id IS NULL
    LOOP
        INSERT INTO conversaciones (usuario_id, titulo, creada_en, actualizada_en)
        VALUES (fila.usuario_id, left(fila.texto, 120), fila.realizada_en, fila.realizada_en)
        RETURNING id INTO nueva;

        UPDATE consultas SET conversacion_id = nueva WHERE id = fila.id;
    END LOOP;
END $$;

UPDATE consultas SET resuelta_en = realizada_en
WHERE estado = 'resuelta' AND resuelta_en IS NULL;

ALTER TABLE consultas ALTER COLUMN conversacion_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_consultas_conversacion
    ON consultas (conversacion_id, realizada_en);

-- El conteo del límite diario filtra por estas dos columnas.
CREATE INDEX IF NOT EXISTS idx_consultas_resueltas
    ON consultas (usuario_id, resuelta_en) WHERE estado = 'resuelta';
