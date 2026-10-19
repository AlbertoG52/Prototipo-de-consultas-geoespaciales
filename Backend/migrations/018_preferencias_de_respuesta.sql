-- Módulo 4 (RR_67, RR_68, RR_79, RR_80): si las respuestas incluyen el mapa y
-- las fuentes.
--
-- RR_80: el supermoderador define el comportamiento por defecto del sistema.
-- Se guarda en una tabla de una sola fila (id = 1) y aplica a todos los que no
-- lo han cambiado: usuarios, visitantes y moderadores sin preferencia propia.
CREATE TABLE IF NOT EXISTS configuracion_respuestas (
    id              SMALLINT    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    incluir_mapa    BOOLEAN     NOT NULL DEFAULT TRUE,
    incluir_fuentes BOOLEAN     NOT NULL DEFAULT TRUE,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Quién hizo el último cambio. NULL = valor inicial o cuenta ya borrada.
    actualizado_por INTEGER     REFERENCES usuarios(id) ON DELETE SET NULL
);

INSERT INTO configuracion_respuestas (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- RR_67, RR_68, RR_79: la preferencia propia de cada moderador sigue en
-- 'usuarios' (migración 007), pero ahora NULL significa "no la ha modificado,
-- usa la del sistema" (criterio 2 de RR_80), igual que minutos_inactividad.
ALTER TABLE usuarios
    ALTER COLUMN incluir_mapa    DROP NOT NULL,
    ALTER COLUMN incluir_mapa    DROP DEFAULT,
    ALTER COLUMN incluir_fuentes DROP NOT NULL,
    ALTER COLUMN incluir_fuentes DROP DEFAULT;

-- Hasta esta migración nadie podía cambiarlas (no había endpoint), así que el
-- TRUE que tenían era solo el valor por defecto de la 007.
UPDATE usuarios
SET incluir_mapa = NULL, incluir_fuentes = NULL
WHERE incluir_mapa IS NOT NULL OR incluir_fuentes IS NOT NULL;
