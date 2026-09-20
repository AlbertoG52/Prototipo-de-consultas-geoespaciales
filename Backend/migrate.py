"""
Aplica en orden los archivos .sql de la carpeta migrations/ que aún no se hayan
aplicado, y lleva el registro en la tabla schema_migrations.
Es idempotente: correrlo varias veces solo aplica lo que falte.
"""
import os
import glob
import sys
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Tabla de control: recuerda qué migraciones ya se aplicaron
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    conn.commit()

    cur.execute("SELECT version FROM schema_migrations;")
    aplicadas = {fila[0] for fila in cur.fetchall()}

    archivos = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    pendientes = [f for f in archivos if os.path.basename(f) not in aplicadas]

    if not pendientes:
        print("  Sin migraciones pendientes.")
        cur.close(); conn.close()
        return

    for ruta in pendientes:
        nombre = os.path.basename(ruta)
        with open(ruta, encoding="utf-8") as fh:
            sql = fh.read()
        try:
            cur.execute(sql)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s);", (nombre,))
            conn.commit()
            print(f"  Aplicada: {nombre}")
        except Exception as e:
            conn.rollback()
            print(f"  ERROR en {nombre}: {e}", file=sys.stderr)
            sys.exit(1)

    cur.close(); conn.close()


if __name__ == "__main__":
    main()
