-- RR_63 y RR_64: el supermoderador define cuántas consultas tiene cada rol y
-- cada cuánto se restablece su contador.
--
-- El contador no se guarda ni se reinicia con un proceso: se cuentan las
-- consultas resueltas dentro del periodo actual (services/uso.py). Así se
-- restablece solo al empezar el periodo siguiente (RR_64 criterio 1).

-- Periodo del contador: 'dia', 'semana' o 'mes' (dominio.PeriodoConsultas).
-- Los roles existentes quedan como estaban: un límite diario.
ALTER TABLE roles
    ADD COLUMN IF NOT EXISTS periodo_consultas VARCHAR(10) NOT NULL DEFAULT 'dia';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'roles_periodo_consultas_valido') THEN
        ALTER TABLE roles ADD CONSTRAINT roles_periodo_consultas_valido
            CHECK (periodo_consultas IN ('dia', 'semana', 'mes'));
    END IF;
    -- RR_63 criterio 3: un límite debe ser un número válido de consultas.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'roles_limite_consultas_valido') THEN
        ALTER TABLE roles ADD CONSTRAINT roles_limite_consultas_valido
            CHECK (limite_consultas BETWEEN 1 AND 100000);
    END IF;
END $$;

-- RR_00_09: los cambios de límite quedan en la auditoría, con quién los hizo
-- (app.actor_id, igual que en 011). No afectan a un usuario en particular, así
-- que usuario_afectado_id queda en NULL y el detalle dice qué rol cambió.
CREATE OR REPLACE FUNCTION registrar_auditoria_rol()
RETURNS TRIGGER AS $$
DECLARE
    actor INTEGER := NULLIF(current_setting('app.actor_id', true), '')::INTEGER;
BEGIN
    IF NEW.limite_consultas IS DISTINCT FROM OLD.limite_consultas
       OR NEW.periodo_consultas IS DISTINCT FROM OLD.periodo_consultas THEN
        INSERT INTO auditoria (usuario_afectado_id, actor_id, accion, detalle)
        VALUES (NULL, actor, 'cambio_limite',
                NEW.nombre || ': ' ||
                OLD.limite_consultas || ' por ' ||
                CASE OLD.periodo_consultas WHEN 'dia' THEN 'día' ELSE OLD.periodo_consultas END ||
                ' -> ' ||
                NEW.limite_consultas || ' por ' ||
                CASE NEW.periodo_consultas WHEN 'dia' THEN 'día' ELSE NEW.periodo_consultas END);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_roles_auditoria ON roles;
CREATE TRIGGER trg_roles_auditoria
    AFTER UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION registrar_auditoria_rol();
