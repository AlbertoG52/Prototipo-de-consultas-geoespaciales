-- Contador diario del visitante sin cuenta.
--
-- Guarda solo cuántas consultas lleva por día, nunca el texto ni la respuesta. 'anon_id' es
-- un UUID aleatorio que viaja firmado en el token anónimo; no identifica a una persona.
CREATE TABLE IF NOT EXISTS consumo_anonimo (
    anon_id              VARCHAR(64) NOT NULL,
    fecha                DATE        NOT NULL DEFAULT CURRENT_DATE,
    consultas_realizadas INTEGER     NOT NULL DEFAULT 0,
    PRIMARY KEY (anon_id, fecha)
);

-- Permite borrar los contadores viejos sin recorrer toda la tabla.
CREATE INDEX IF NOT EXISTS idx_consumo_anonimo_fecha ON consumo_anonimo(fecha);
