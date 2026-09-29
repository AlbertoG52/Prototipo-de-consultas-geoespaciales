-- RR_00_09: la auditoría registra quién hizo el cambio y no se puede alterar.

-- Quién hizo el cambio. NULL = desde el servidor (p. ej. cambiar_rol.py).
ALTER TABLE auditoria
    ADD COLUMN IF NOT EXISTS actor_id INTEGER REFERENCES usuarios(id);

-- Reemplaza la función de 003. El actor lo define la API en la misma
-- transacción con set_config('app.actor_id', ...). El detalle usa el nombre
-- del rol en vez de su id.
CREATE OR REPLACE FUNCTION registrar_auditoria_usuario()
RETURNS TRIGGER AS $$
DECLARE
    actor INTEGER := NULLIF(current_setting('app.actor_id', true), '')::INTEGER;
BEGIN
    IF NEW.rol_id IS DISTINCT FROM OLD.rol_id THEN
        INSERT INTO auditoria (usuario_afectado_id, actor_id, accion, detalle)
        VALUES (NEW.id, actor, 'cambio_rol',
                (SELECT nombre FROM roles WHERE id = OLD.rol_id) || ' -> ' ||
                (SELECT nombre FROM roles WHERE id = NEW.rol_id));
    END IF;
    IF NEW.estado IS DISTINCT FROM OLD.estado THEN
        INSERT INTO auditoria (usuario_afectado_id, actor_id, accion, detalle)
        VALUES (NEW.id, actor, 'cambio_estado', OLD.estado || ' -> ' || NEW.estado);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- El registro no se puede editar ni borrar. Excepción: el dueño de la BD aún
-- podría eliminar este trigger; impedirlo requiere que la app use un usuario
-- de BD sin privilegios de dueño.
CREATE OR REPLACE FUNCTION bloquear_cambios_auditoria()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'El registro de auditoría no se puede modificar ni eliminar.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON auditoria;
CREATE TRIGGER trg_auditoria_inmutable
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION bloquear_cambios_auditoria();

DROP TRIGGER IF EXISTS trg_auditoria_sin_truncate ON auditoria;
CREATE TRIGGER trg_auditoria_sin_truncate
    BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION bloquear_cambios_auditoria();
