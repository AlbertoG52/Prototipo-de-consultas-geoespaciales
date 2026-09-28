-- Módulo 1 (RR_09): historial de consultas de la sesión activa.
--
-- 'sesion_id' identifica la sesión en la que se hizo la consulta. Se genera al
-- iniciar sesión y viaja dentro del token, de modo que el historial se puede
-- filtrar por la sesión activa y no por todo el histórico del usuario, que es
-- justo lo que pide el criterio 3 del requerimiento.
--
-- 'respuesta' guarda el resultado ya armado. El criterio 2 pide que el usuario
-- pueda volver a ver una respuesta anterior sin repetir la consulta: sin esta
-- columna habría que reprocesarla, que es precisamente lo que se quiere evitar.
ALTER TABLE consultas
    ADD COLUMN IF NOT EXISTS sesion_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS respuesta JSONB;

CREATE INDEX IF NOT EXISTS idx_consultas_sesion ON consultas(sesion_id);
