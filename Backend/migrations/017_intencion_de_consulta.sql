-- Intención detectada en cada consulta, para monitoreo.
--
-- Va en tiempos_respuesta, que tiene una fila por cada consulta de cuentas y visitantes. No
-- guarda el texto.
--
-- Valores (dominio.IntencionConsulta):
--   distribucion, habitat, descripcion, general   consulta sobre una especie
--   sin_sentido, idioma, ayuda, saludo,          mensaje que no es una consulta
--   fuera_de_tema
--
-- Las filas anteriores quedan sin intención (NULL).

ALTER TABLE tiempos_respuesta ADD COLUMN IF NOT EXISTS intencion VARCHAR(20);

ALTER TABLE tiempos_respuesta DROP CONSTRAINT IF EXISTS tiempos_respuesta_intencion_valida;
ALTER TABLE tiempos_respuesta ADD CONSTRAINT tiempos_respuesta_intencion_valida
    CHECK (intencion IS NULL OR intencion IN (
        'distribucion', 'habitat', 'descripcion', 'general',
        'sin_sentido', 'idioma', 'ayuda', 'saludo', 'fuera_de_tema'
    ));

-- Para contar por intención en un periodo (GET /admin/tiempos).
CREATE INDEX IF NOT EXISTS idx_tiempos_respuesta_intencion
    ON tiempos_respuesta (intencion, registrada_en DESC);
