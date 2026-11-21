-- Nombre completo del usuario. Es opcional para no afectar las filas existentes.
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS nombre VARCHAR(120);
