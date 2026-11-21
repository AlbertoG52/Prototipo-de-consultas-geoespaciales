-- Sesión de cada consulta y su respuesta.
--
-- 'sesion_id' se genera al iniciar sesión y viaja en el token. 'respuesta' guarda el
-- resultado armado, para volver a verlo sin reprocesar la consulta.
ALTER TABLE consultas
    ADD COLUMN IF NOT EXISTS sesion_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS respuesta JSONB;

CREATE INDEX IF NOT EXISTS idx_consultas_sesion ON consultas(sesion_id);
