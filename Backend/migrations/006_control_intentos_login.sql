-- Módulo 0 (RR_00_05): bloqueo temporal por intentos fallidos de inicio de sesión.
-- Se resuelve con columnas en 'usuarios' (más simple que una tabla de historial).
-- 'ultimo_acceso' apoya el control de expiración de sesión por inactividad (RR_00_04).
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS intentos_fallidos INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bloqueado_hasta   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ultimo_acceso     TIMESTAMPTZ;
