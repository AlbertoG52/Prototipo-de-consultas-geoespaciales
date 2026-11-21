-- El inicio de sesión exige el correo verificado. Las cuentas creadas antes de la
-- verificación se marcan como verificadas; las nuevas empiezan sin verificar.
UPDATE usuarios SET correo_verificado = TRUE WHERE correo_verificado = FALSE;
