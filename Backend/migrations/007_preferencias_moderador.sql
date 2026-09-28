-- Módulo 4 (RR_67, RR_68): el moderador configura si sus respuestas incluyen
-- el mapa y las fuentes. Al ser pocas opciones, van como columnas en 'usuarios'.
-- Los valores por defecto definen el comportamiento inicial del sistema (RR_80).
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS incluir_mapa    BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS incluir_fuentes BOOLEAN NOT NULL DEFAULT TRUE;
