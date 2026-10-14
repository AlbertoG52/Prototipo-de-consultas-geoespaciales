-- RR_22, RR_32, RR_37 y RR_40: consultas que no se procesan y se responden
-- orientando al usuario (saludo, ayuda, otro idioma, sin sentido, fuera de tema).
--
-- Se agrega un cuarto estado, 'orientacion', y la columna 'motivo' con el porqué
-- (dominio.MotivoOrientacion). Igual que 'ambigua' y 'sin_coincidencias', se
-- guarda en la conversación pero no descuenta del límite diario: el conteo solo
-- mira las 'resuelta' (idx_consultas_resueltas, 012).
--
--   estado             motivo
--   resuelta           NULL
--   ambigua            NULL
--   sin_coincidencias  NULL
--   orientacion        sin_sentido | idioma | ayuda | saludo | fuera_de_tema

ALTER TABLE consultas DROP CONSTRAINT IF EXISTS consultas_estado_valido;
ALTER TABLE consultas ADD CONSTRAINT consultas_estado_valido
    CHECK (estado IN ('resuelta', 'ambigua', 'sin_coincidencias', 'orientacion'));

ALTER TABLE consultas ADD COLUMN IF NOT EXISTS motivo VARCHAR(20);

-- Un motivo válido, y solo en las de orientación (y en todas ellas).
ALTER TABLE consultas DROP CONSTRAINT IF EXISTS consultas_motivo_valido;
ALTER TABLE consultas ADD CONSTRAINT consultas_motivo_valido
    CHECK (
        (estado = 'orientacion') = (motivo IS NOT NULL)
        AND (motivo IS NULL
             OR motivo IN ('sin_sentido', 'idioma', 'ayuda', 'saludo', 'fuera_de_tema'))
    );
