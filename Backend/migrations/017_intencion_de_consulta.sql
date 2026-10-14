-- RR_33: registro interno de la intención detectada en cada consulta, para
-- monitoreo y mejora (y RR_29 criterio 3: el tipo de consulta detectado).
--
-- Va en tiempos_respuesta (015) porque esa tabla ya tiene una fila por CADA
-- POST /consultas, termine bien o mal, de cuentas y de visitantes, con su id
-- único (criterio 2) y, para una cuenta, el enlace a la consulta guardada
-- (consulta_id). No guarda el texto: del visitante solo queda qué intentó
-- hacer, no qué escribió (RR_00_11).
--
-- Valores (dominio.IntencionConsulta):
--   distribucion, habitat, descripcion, general   consulta sobre una especie (RR_29)
--   sin_sentido, idioma, ayuda, saludo,          mensaje que no es una consulta
--   fuera_de_tema                                (RR_22, RR_32, RR_37, RR_40)
--
-- Las filas anteriores a esta migración quedan sin intención (NULL).

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
