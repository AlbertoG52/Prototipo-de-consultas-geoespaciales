-- Módulo 0 (RR_00_07): verificación de correo electrónico.
-- Desde ahora el login exige el correo verificado. Las cuentas creadas antes
-- de que existiera la verificación se consideran verificadas, para no dejar
-- fuera a sus dueños (supermoderador, cuentas del equipo, correos de prueba).
-- Se aplica una sola vez; las cuentas nuevas empiezan sin verificar.
UPDATE usuarios SET correo_verificado = TRUE WHERE correo_verificado = FALSE;
