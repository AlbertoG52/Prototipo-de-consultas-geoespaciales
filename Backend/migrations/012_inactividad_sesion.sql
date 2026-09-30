-- RR_00_04: expiración de la sesión por inactividad.
-- Minutos sin actividad tras los cuales se cierra la sesión de este usuario.
--   NULL = usa el valor por defecto del sistema (MINUTOS_INACTIVIDAD_SESION).
--   0    = "Nunca" (la sesión no expira por inactividad).
-- Los valores permitidos los valida la API (config.OPCIONES_INACTIVIDAD).
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS minutos_inactividad INTEGER
        CHECK (minutos_inactividad IS NULL OR minutos_inactividad >= 0);
