# certs/ — acceso a la base de datos de AWS (En caso de escalar)

La base de datos de AWS es un PostgreSQL que corre dentro de una instancia EC2. No está
abierta a Internet: se accede por SSH con una llave `.pem`, que se guarda en esta carpeta.
Solo se necesita para el modo AWS; el desarrollo diario usa la base local.

## Funcionamiento

```
 equipo local                                            EC2 (AWS)
┌─────────────────────────────────┐   túnel SSH (22)   ┌──────────────────┐
│ backend (Docker)                │ ═════════════════► │ Postgres :5432   │
│   └─► host.docker.internal:5433 ─┼─ ssh -L 5433 ... ─┤ (solo localhost) │
└─────────────────────────────────┘                    └──────────────────┘
```

El comando `ssh -L` abre un túnel: lo que llega al puerto 5433 del equipo local sale por SSH
hacia el PostgreSQL de la EC2. El backend, desde Docker, se conecta a
`host.docker.internal:5433`. Si el túnel se cierra, el backend pierde la conexión.

| Modo | Comando | Base de datos | Uso |
|---|---|---|---|
| Local | `docker compose up --build` | PostgreSQL en Docker | Desarrollo y pruebas |
| AWS | túnel SSH + `docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build` | PostgreSQL en la EC2 | Demostraciones e integración |

Levante el modo AWS solo desde la rama principal: al arrancar, el backend aplica las
migraciones pendientes en la base compartida.

## Configuración inicial

1. **Obtenga los datos de acceso** con quien administra la EC2:

   | Dato | Ejemplo |
   |---|---|
   | Llave `.pem` | `llave-aws.pem` |
   | IP pública o DNS de la EC2 | `3.85.120.14` |
   | Usuario SSH | `ubuntu` (Ubuntu) o `ec2-user` (Amazon Linux) |
   | Usuario, clave y nombre de la base | `flora` / `****` / `flora_db` |

2. **Guarde la llave** como `certs/llave-aws.pem` y restrinja sus permisos. En Windows, desde
   la raíz del proyecto, en PowerShell:

   ```powershell
   icacls certs\llave-aws.pem /inheritance:r
   icacls certs\llave-aws.pem /grant:r "$($env:USERNAME):(R)"
   ```

3. **Pruebe el acceso SSH**:

   ```powershell
   ssh -i certs/llave-aws.pem USUARIO_EC2@IP_EC2
   ```

   Si entra, escriba `exit`. Si se queda esperando, el *security group* de la EC2 no permite
   el puerto 22 desde su IP.

4. **Agregue `DATABASE_URL_AWS` al `.env`** de la raíz del proyecto:

   ```
   DATABASE_URL_AWS=postgresql://USUARIO_BD:CLAVE_BD@host.docker.internal:5433/NOMBRE_BD
   ```

   Use el usuario, la clave y el nombre de PostgreSQL (no los de SSH) y no cambie
   `host.docker.internal:5433`. Si la clave tiene caracteres especiales, codifíquelos:
   `@` → `%40`, `:` → `%3A`, `/` → `%2F`, `#` → `%23`, `%` → `%25`.

5. **Verifique Docker Compose 2.24.4 o superior** con `docker compose version`.

## Levantar en modo AWS

Se necesitan dos terminales.

**Terminal 1 — túnel** (debe quedar abierta):

```powershell
ssh -i certs/llave-aws.pem -N -L 5433:localhost:5432 USUARIO_EC2@IP_EC2
```

**Terminal 2 — proyecto:**

```powershell
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```

Para confirmar que usa la base de AWS: `docker compose ps` no debe mostrar el contenedor
`db`, y http://localhost:8000/db-check debe responder `"conexion": "ok"`. Para volver al
modo local, cierre el túnel (`Ctrl+C`) y use `docker compose up`.

## Acceso a la base con psql

**Dentro de la EC2** (no necesita el túnel):

```bash
ssh -i certs/llave-aws.pem USUARIO_EC2@IP_EC2
sudo -u postgres psql -d NOMBRE_BD
```

Si PostgreSQL corre en Docker dentro de la EC2, identifique el contenedor con `sudo docker ps`
y use `sudo docker exec -it <contenedor> psql -U USUARIO_BD -d NOMBRE_BD`.

**Desde el equipo local, por el túnel** (con la terminal 1 abierta):

```powershell
docker run --rm -it postgres:16 psql -h host.docker.internal -p 5433 -U USUARIO_BD -d NOMBRE_BD
```

## Reiniciar la base

Esta operación borra todos los datos de la base de AWS y no se puede deshacer.

1. Detenga el backend (`docker compose down`).
2. En `psql`:

   ```sql
   DROP SCHEMA public CASCADE;
   CREATE SCHEMA public;
   ```

   Se borra también `schema_migrations`, para que las migraciones vuelvan a aplicarse.
3. Levante otra vez el modo AWS: las migraciones recrean todas las tablas.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `UNPROTECTED PRIVATE KEY FILE` | Faltan los permisos del paso 2 |
| `Permission denied (publickey)` | Usuario SSH o llave incorrectos |
| SSH se queda esperando | El *security group* no permite el puerto 22 desde su IP |
| `bind [127.0.0.1]:5433: Address already in use` | Ya hay un túnel abierto u otro programa usa el puerto 5433 |
| `Falta DATABASE_URL_AWS` | Falta el paso 4 |
| `connection refused` en `host.docker.internal:5433` | El túnel no está abierto |
| `password authentication failed` | Usuario o clave de PostgreSQL incorrectos, o clave sin codificar |
| Error de sintaxis con `!reset` | Docker Compose anterior a 2.24.4 |
