-- Módulo 0 (RR_00_01): la vista de registro pide "Nombre completo" y la tabla
-- usuarios no tenía dónde guardarlo. Se agrega como columna opcional para no
-- romper las filas que ya existan; el registro nuevo siempre la envía.
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS nombre VARCHAR(120);
