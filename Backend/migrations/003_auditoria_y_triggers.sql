-- Módulo 0 (RR_00_09): auditoría de acciones administrativas
CREATE TABLE IF NOT EXISTS auditoria (
    id                  SERIAL PRIMARY KEY,
    usuario_afectado_id INTEGER REFERENCES usuarios(id),
    accion              VARCHAR(100) NOT NULL,
    detalle             TEXT,
    fecha               TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Trigger 1: mantener actualizado_en al día en cada UPDATE de usuarios
CREATE OR REPLACE FUNCTION set_actualizado_en()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_usuarios_actualizado ON usuarios;
CREATE TRIGGER trg_usuarios_actualizado
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION set_actualizado_en();

-- Trigger 2: registrar en auditoría los cambios de rol o de estado
CREATE OR REPLACE FUNCTION registrar_auditoria_usuario()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.rol_id IS DISTINCT FROM OLD.rol_id THEN
        INSERT INTO auditoria (usuario_afectado_id, accion, detalle)
        VALUES (NEW.id, 'cambio_rol', 'rol ' || OLD.rol_id || ' -> ' || NEW.rol_id);
    END IF;
    IF NEW.estado IS DISTINCT FROM OLD.estado THEN
        INSERT INTO auditoria (usuario_afectado_id, accion, detalle)
        VALUES (NEW.id, 'cambio_estado', 'estado ' || OLD.estado || ' -> ' || NEW.estado);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_usuarios_auditoria ON usuarios;
CREATE TRIGGER trg_usuarios_auditoria
    AFTER UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION registrar_auditoria_usuario();
