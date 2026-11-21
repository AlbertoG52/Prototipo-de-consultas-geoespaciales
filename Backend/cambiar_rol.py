"""Cambia el rol de una cuenta existente desde el servidor.

El registro siempre crea cuentas con rol 'usuario'; este script permite crear el primer
supermoderador o recuperar el acceso si no queda ninguno activo. Requiere acceso al
contenedor.

Uso: docker compose exec backend python cambiar_rol.py <correo> <rol>

Roles válidos: usuario, moderador, supermoderador. El cambio queda en 'auditoria' sin
actor.
"""

import os
import sys

import psycopg2

from app.dominio import EstadoCuenta, NombreRol

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
                WHERE r.nombre = %s AND u.estado = %s;
                """,
                (NombreRol.SUPERMODERADOR, EstadoCuenta.ACTIVO),
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
