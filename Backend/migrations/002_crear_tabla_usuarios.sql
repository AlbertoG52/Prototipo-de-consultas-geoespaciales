-- Usuarios y autenticación.
CREATE TABLE IF NOT EXISTS usuarios (
    id                   SERIAL PRIMARY KEY,
    correo               VARCHAR(255) NOT NULL UNIQUE,
    password_hash        VARCHAR(255) NOT NULL, -- hash bcrypt de la contraseña
    rol_id               INTEGER      NOT NULL REFERENCES roles(id),
    estado               VARCHAR(20)  NOT NULL DEFAULT 'activo'
                          CHECK (estado IN ('activo', 'inactivo')), -- activo o inactivo
    correo_verificado    BOOLEAN      NOT NULL DEFAULT FALSE, -- correo confirmado
    consultas_realizadas INTEGER      NOT NULL DEFAULT 0, -- sin uso: las consultas se cuentan por filas
    creado_en            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actualizado_en       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_correo ON usuarios(correo);
