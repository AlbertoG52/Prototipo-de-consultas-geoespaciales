-- Si las respuestas incluyen el mapa y las fuentes.
--
-- El supermoderador define el comportamiento por defecto en una tabla de una sola fila (id
-- = 1). Aplica a todos los que no tienen preferencia propia.
CREATE TABLE IF NOT EXISTS configuracion_respuestas (
    id              SMALLINT    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    incluir_mapa    BOOLEAN     NOT NULL DEFAULT TRUE,
    incluir_fuentes BOOLEAN     NOT NULL DEFAULT TRUE,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Quién hizo el último cambio. NULL = valor inicial o cuenta ya borrada.
    actualizado_por INTEGER     REFERENCES usuarios(id) ON DELETE SET NULL
);

INSERT INTO configuracion_respuestas (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- La preferencia de cada moderador sigue en 'usuarios'; NULL significa que usa la del
-- sistema.
ALTER TABLE usuarios
    ALTER COLUMN incluir_mapa    DROP NOT NULL,
    ALTER COLUMN incluir_mapa    DROP DEFAULT,
    ALTER COLUMN incluir_fuentes DROP NOT NULL,
    ALTER COLUMN incluir_fuentes DROP DEFAULT;

-- Hasta aquí nadie podía cambiarlas, así que el TRUE guardado era solo el valor por
-- defecto.
UPDATE usuarios
SET incluir_mapa = NULL, incluir_fuentes = NULL
WHERE incluir_mapa IS NOT NULL OR incluir_fuentes IS NOT NULL;
