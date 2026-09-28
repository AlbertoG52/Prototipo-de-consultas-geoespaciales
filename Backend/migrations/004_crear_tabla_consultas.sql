-- Módulo 4: registro de consultas realizadas.
-- Permite contar el uso (RR_66 consultas restantes), mostrar el historial
-- por usuario al supermoderador (RR_76) y respaldar el límite por rol (RR_62).
CREATE TABLE IF NOT EXISTS consultas (
    id           SERIAL PRIMARY KEY,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    texto        TEXT NOT NULL,
    realizada_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consultas_usuario ON consultas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_consultas_fecha   ON consultas(realizada_en);
