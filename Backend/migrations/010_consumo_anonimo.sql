-- Módulo 0 (RR_00_11): acceso público sin cuenta.
--
-- El visitante anónimo tiene un límite diario menor que el del usuario
-- registrado (criterio 3), así que hay que contar sus consultas. Pero el
-- criterio 1 dice que el sistema NO almacena sus consultas anteriores.
--
-- Por eso esta tabla guarda únicamente un contador por día: nunca el texto de
-- la consulta ni su respuesta. El historial del visitante vive solo en la
-- memoria del navegador y desaparece al recargar, que es el comportamiento
-- que el requerimiento describe.
--
-- 'anon_id' es un UUID aleatorio que el servidor emite en la primera visita y
-- que viaja firmado dentro del token anónimo. No identifica a una persona.
CREATE TABLE IF NOT EXISTS consumo_anonimo (
    anon_id              VARCHAR(64) NOT NULL,
    fecha                DATE        NOT NULL DEFAULT CURRENT_DATE,
    consultas_realizadas INTEGER     NOT NULL DEFAULT 0,
    PRIMARY KEY (anon_id, fecha)
);

-- Permite borrar los contadores viejos sin recorrer toda la tabla.
CREATE INDEX IF NOT EXISTS idx_consumo_anonimo_fecha ON consumo_anonimo(fecha);
