-- Si las respuestas del moderador incluyen el mapa y las fuentes.
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS incluir_mapa    BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS incluir_fuentes BOOLEAN NOT NULL DEFAULT TRUE;
