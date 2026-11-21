-- Tokens temporales:
-- 'verificacion' -> confirmar el correo al registrarse
-- 'recuperacion' -> restablecer la contraseña olvidada
CREATE TABLE IF NOT EXISTS tokens (
    id         SERIAL PRIMARY KEY,
    usuario_id INTEGER      NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token      VARCHAR(255) NOT NULL UNIQUE,
    tipo       VARCHAR(20)  NOT NULL CHECK (tipo IN ('verificacion', 'recuperacion')),
    expira_en  TIMESTAMPTZ  NOT NULL,                 -- vence tras un tiempo limitado
    usado      BOOLEAN      NOT NULL DEFAULT FALSE,    -- un token se usa una sola vez
    creado_en  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tokens_token   ON tokens(token);
CREATE INDEX IF NOT EXISTS idx_tokens_usuario ON tokens(usuario_id);
