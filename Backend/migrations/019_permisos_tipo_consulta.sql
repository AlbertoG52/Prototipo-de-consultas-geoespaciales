-- Módulo 4 (RR_77): tipos de consulta permitidos por rol.
--
-- El supermoderador decide qué tipos de pregunta (dominio.TipoPregunta) puede
-- hacer cada rol. Se configuran el visitante sin cuenta, el usuario y el
-- moderador; el supermoderador siempre puede todo, para que no pueda
-- bloquearse a sí mismo. Al inicio todo está permitido.
--
--   rol     visitante | usuario | moderador
--   tipo    distribucion | habitat | descripcion | general
CREATE TABLE IF NOT EXISTS permisos_tipo_consulta (
    rol             VARCHAR(20) NOT NULL
        CHECK (rol IN ('visitante', 'usuario', 'moderador')),
    tipo            VARCHAR(20) NOT NULL
        CHECK (tipo IN ('distribucion', 'habitat', 'descripcion', 'general')),
    permitido       BOOLEAN     NOT NULL DEFAULT TRUE,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Quién hizo el último cambio. NULL = valor inicial o cuenta ya borrada.
    actualizado_por INTEGER     REFERENCES usuarios(id) ON DELETE SET NULL,
    PRIMARY KEY (rol, tipo)
);

INSERT INTO permisos_tipo_consulta (rol, tipo)
SELECT rol, tipo
FROM (VALUES ('visitante'), ('usuario'), ('moderador')) AS r (rol)
CROSS JOIN (VALUES ('distribucion'), ('habitat'), ('descripcion'), ('general')) AS t (tipo)
ON CONFLICT (rol, tipo) DO NOTHING;

-- Una consulta de un tipo no permitido se responde orientando al usuario, con
-- el motivo 'tipo_no_permitido' (amplía la restricción de 016). Igual que las
-- demás orientaciones, no descuenta del límite diario.
ALTER TABLE consultas DROP CONSTRAINT IF EXISTS consultas_motivo_valido;
ALTER TABLE consultas ADD CONSTRAINT consultas_motivo_valido
    CHECK (
        (estado = 'orientacion') = (motivo IS NOT NULL)
        AND (motivo IS NULL
             OR motivo IN ('sin_sentido', 'idioma', 'ayuda', 'saludo', 'fuera_de_tema',
                           'tipo_no_permitido'))
    );

-- RR_00_09: cada cambio de permiso queda en la auditoría, con quién lo hizo
-- (app.actor_id, igual que los cambios de rol y de estado de 011). No hay
-- usuario afectado: el cambio es de un rol completo.
CREATE OR REPLACE FUNCTION registrar_auditoria_permiso()
RETURNS TRIGGER AS $$
DECLARE
    actor INTEGER := NULLIF(current_setting('app.actor_id', true), '')::INTEGER;
BEGIN
    INSERT INTO auditoria (usuario_afectado_id, actor_id, accion, detalle)
    VALUES (NULL, actor, 'cambio_permiso',
            NEW.rol || ' · ' ||
            CASE NEW.tipo
                WHEN 'distribucion' THEN 'distribución'
                WHEN 'habitat'      THEN 'hábitat'
                WHEN 'descripcion'  THEN 'descripción'
                ELSE NEW.tipo
            END || ': ' ||
            CASE WHEN OLD.permitido THEN 'permitido' ELSE 'no permitido' END || ' -> ' ||
            CASE WHEN NEW.permitido THEN 'permitido' ELSE 'no permitido' END);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_permisos_tipo_consulta_auditoria ON permisos_tipo_consulta;
CREATE TRIGGER trg_permisos_tipo_consulta_auditoria
    AFTER UPDATE ON permisos_tipo_consulta
    FOR EACH ROW
    WHEN (OLD.permitido IS DISTINCT FROM NEW.permitido)
    EXECUTE FUNCTION registrar_auditoria_permiso();
