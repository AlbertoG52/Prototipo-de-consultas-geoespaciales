-- Bloqueo temporal por intentos fallidos de inicio de sesión, y último acceso.
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS intentos_fallidos INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bloqueado_hasta   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ultimo_acceso     TIMESTAMPTZ;
