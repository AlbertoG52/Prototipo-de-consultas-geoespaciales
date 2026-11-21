-- Minutos sin actividad tras los cuales se cierra la sesión del usuario:
--   NULL = valor por defecto del sistema (MINUTOS_INACTIVIDAD_SESION)
--   0    = "Nunca"
-- Los valores permitidos los valida la API (config.OPCIONES_INACTIVIDAD).
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS minutos_inactividad INTEGER
        CHECK (minutos_inactividad IS NULL OR minutos_inactividad >= 0);
