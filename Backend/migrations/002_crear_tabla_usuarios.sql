-- Módulo 0: usuarios y autenticación
CREATE TABLE IF NOT EXISTS usuarios (
    id                   SERIAL PRIMARY KEY,
    correo               VARCHAR(255) NOT NULL UNIQUE,
    password_hash        VARCHAR(255) NOT NULL,          -- bcrypt, para la contraseña (RR_00_02)
    rol_id               INTEGER      NOT NULL REFERENCES roles(id),
    estado               VARCHAR(20)  NOT NULL DEFAULT 'activo'
                          CHECK (estado IN ('activo', 'inactivo')),   -- RR_74 / RR_75
    correo_verificado    BOOLEAN      NOT NULL DEFAULT FALSE,          -- RR_00_07
    consultas_realizadas INTEGER      NOT NULL DEFAULT 0,              -- para el control de límite (RR_66)
    creado_en            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actualizado_en       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_correo ON usuarios(correo);
