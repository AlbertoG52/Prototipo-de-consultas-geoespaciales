-- Módulo 4: roles del sistema (usuario / moderador / supermoderador)
-- Va primero porque la tabla usuarios lo referencia por llave foránea.
CREATE TABLE IF NOT EXISTS roles (
    id               SERIAL PRIMARY KEY,
    nombre           VARCHAR(50)  NOT NULL UNIQUE,
    descripcion      VARCHAR(200),
    limite_consultas INTEGER      NOT NULL DEFAULT 20
);

-- Roles base del sistema
INSERT INTO roles (nombre, descripcion, limite_consultas) VALUES
    ('usuario',        'Usuario estándar',              20),
    ('moderador',      'Puede configurar sus respuestas', 100),
    ('supermoderador', 'Administra usuarios y roles',   1000)
ON CONFLICT (nombre) DO NOTHING;
