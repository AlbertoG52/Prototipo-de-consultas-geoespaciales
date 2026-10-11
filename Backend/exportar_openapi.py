"""Escribe el contrato OpenAPI del backend en un archivo JSON.

El frontend genera sus tipos de TypeScript a partir de este contrato
(Frontend/src/types/api.ts, con `npm run tipos`), así un cambio en un esquema
de Pydantic se refleja en el frontend sin copiarlo a mano. No necesita la base
de datos: solo importa la aplicación.

    python exportar_openapi.py ../Frontend/openapi.json
"""

import json
import os
import sys

# La configuración exige DATABASE_URL, pero exportar el contrato no se conecta.
os.environ.setdefault("DATABASE_URL", "postgresql://sin-conexion/flora")

from app.main import app


def main() -> None:
    destino = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    with open(destino, "w", encoding="utf-8", newline="\n") as archivo:
        json.dump(app.openapi(), archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")
    print(f"Contrato OpenAPI escrito en {destino}")


if __name__ == "__main__":
    main()
