-- Consultas realizadas: base del conteo del límite, del historial y del uso por rol.
CREATE TABLE IF NOT EXISTS consultas (
    id           SERIAL PRIMARY KEY,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    texto        TEXT NOT NULL,
    realizada_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consultas_usuario ON consultas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_consultas_fecha   ON consultas(realizada_en);
