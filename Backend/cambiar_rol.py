"""
Cambia el rol de una cuenta existente desde el servidor —  RR_00_10.

El registro público siempre crea cuentas con rol 'usuario', así que esta es la
forma de obtener el primer supermoderador, y de recuperar el acceso si en
algún momento no queda ninguno activo. Requiere acceso al contenedor: nadie
puede darse más permisos desde la aplicación.

Uso:
    docker compose exec backend python cambiar_rol.py <correo> <rol>

Roles válidos: los de la tabla 'roles' (usuario, moderador, supermoderador).
El cambio queda registrado en 'auditoria' por el trigger de 003, sin actor,
porque no lo hace ningún usuario de la aplicación.
"""
import os
import sys

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    correo = sys.argv[1].strip().lower()
    rol = sys.argv[2].strip().lower()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM roles WHERE nombre = %s;", (rol,))
            fila_rol = cur.fetchone()
            if fila_rol is None:
                cur.execute("SELECT nombre FROM roles ORDER BY id;")
                validos = ", ".join(f[0] for f in cur.fetchall())
                print(f"Rol desconocido: '{rol}'. Válidos: {validos}.", file=sys.stderr)
                return 1

            cur.execute(
                "UPDATE usuarios SET rol_id = %s WHERE correo = %s RETURNING id;",
                (fila_rol[0], correo),
            )
            if cur.fetchone() is None:
                print(f"No existe una cuenta con el correo '{correo}'.", file=sys.stderr)
                return 1

            cur.execute(
                """
                SELECT count(*) FROM usuarios u JOIN roles r ON r.id = u.rol_id
                WHERE r.nombre = 'supermoderador' AND u.estado = 'activo';
                """
            )
            activos = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"Rol de '{correo}' cambiado a '{rol}'.")
    if activos == 0:
        print(
            "Aviso: no queda ningún supermoderador activo; "
            "nadie podrá administrar desde la aplicación.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
