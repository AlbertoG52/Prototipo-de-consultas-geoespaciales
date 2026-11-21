-- Quita de usuarios dos columnas que la aplicación no usa: el límite se calcula contando las
-- consultas resueltas y la inactividad se controla con el vencimiento del token.
ALTER TABLE usuarios
    DROP COLUMN IF EXISTS consultas_realizadas,
    DROP COLUMN IF EXISTS ultimo_acceso;
