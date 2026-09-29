# certs/ — acceso a la base de datos de AWS

La base de datos compartida es un **Postgres que corre dentro de una EC2 de
AWS**. No está abierta a Internet: se llega a ella por **SSH** con una llave
`.pem`. Esta carpeta es donde cada quien guarda esa llave.

Solo hace falta para el **modo AWS**: demos e integración. Para el desarrollo
diario no se necesita nada de esto.

> **Lo único que se sube a Git de esta carpeta es este README.**
> El `.gitignore` ignora todo lo demás (`certs/*`) y cualquier `*.pem` del repo.
> La llave `.pem` es **privada**: quien la tenga puede entrar al servidor.

---

## Cómo funciona

```
 tu máquina                                              EC2 (AWS)
┌─────────────────────────────────┐   túnel SSH (22)   ┌──────────────────┐
│ backend (Docker)                │ ═════════════════► │ Postgres :5432   │
│   └─► host.docker.internal:5433 ─┼─ ssh -L 5433 ... ─┤ (solo localhost) │
└─────────────────────────────────┘                    └──────────────────┘
```

1. El comando `ssh -L` abre un túnel: todo lo que llegue al puerto **5433 de tu
   máquina** sale por SSH y llega al Postgres de la EC2.
2. El backend, desde dentro de Docker, se conecta a `host.docker.internal:5433`,
   que es tu máquina vista desde el contenedor.
3. Si el túnel se cierra, el backend pierde la base.

---

## Cuándo se usa cada modo

| Modo | Comando | Base de datos | Para qué |
|---|---|---|---|
| Local (el de siempre) | `docker compose up --build` | Postgres en Docker, uno por persona | Programar y probar |
| AWS | túnel SSH + `docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build` | Postgres en la EC2, compartida | Demos e integración |

**Regla:** el modo AWS se levanta **solo desde `main`**. Al arrancar, el backend
aplica las migraciones pendientes. Si alguien lo levanta desde su rama, una
migración a medio hacer queda aplicada en la base que usa todo el equipo.

---

## Configuración (una vez por persona)

### 1. Datos que necesitás

Pedíselos a quien administra la EC2:

| Dato | Ejemplo |
|---|---|
| La llave `.pem` | `llave-aws.pem` |
| IP pública o DNS de la EC2 | `3.85.120.14` o `ec2-3-85-120-14.compute-1.amazonaws.com` |
| Usuario SSH de la EC2 | `ubuntu` (Ubuntu) o `ec2-user` (Amazon Linux) |
| Usuario, clave y nombre de la base Postgres | `flora` / `****` / `flora_db` |

### 2. Guardar la llave y arreglar sus permisos

Guardala como `certs/llave-aws.pem`. (Otra opción es `C:\Users\<tu usuario>\.ssh\`,
fuera de OneDrive; si lo hacés así, cambiá la ruta en los comandos de abajo.)

Windows no deja usar una llave que otros usuarios puedan leer: SSH responde
`UNPROTECTED PRIVATE KEY FILE` y se niega a conectar. Se arregla una vez, en
PowerShell, desde la raíz del proyecto:

```powershell
icacls certs\llave-aws.pem /inheritance:r
icacls certs\llave-aws.pem /grant:r "$($env:USERNAME):(R)"
```

### 3. Probar que SSH entra

```powershell
ssh -i certs/llave-aws.pem USUARIO_EC2@IP_EC2
```

Si entra, escribí `exit` y seguí. Si se queda colgado, el *security group* de la
EC2 no permite el puerto **22** desde tu IP: pedí que la agreguen.

### 4. Agregar `DATABASE_URL_AWS` al `.env`

En el `.env` de la raíz del proyecto (no en `.env.example`):

```
DATABASE_URL_AWS=postgresql://USUARIO_BD:CLAVE_BD@host.docker.internal:5433/NOMBRE_BD
```

- `USUARIO_BD`, `CLAVE_BD`, `NOMBRE_BD`: los de **Postgres**, no los de SSH.
- `host.docker.internal:5433` **no se cambia**: es el túnel.
- ⚠️ Si la clave tiene caracteres especiales (`@ : / ? # & %`), hay que
  escribirlos codificados: `@` → `%40`, `:` → `%3A`, `/` → `%2F`, `#` → `%23`,
  `%` → `%25`.

### 5. Tener Docker Compose 2.24.4 o superior

```powershell
docker compose version
```

---

## Levantar en modo AWS

Se necesitan **dos terminales**.

**Terminal 1 — el túnel** (queda abierta, sin mostrar nada; no la cierres):

```powershell
ssh -i certs/llave-aws.pem -N -L 5433:localhost:5432 USUARIO_EC2@IP_EC2
```

**Terminal 2 — el proyecto:**

```powershell
git checkout main
git pull
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```

Cómo verificar que está usando AWS y no la base local:

- En `docker compose ps` **no** debe aparecer el contenedor `db`.
- http://localhost:8000/db-check debe responder `"conexion": "ok"`.

Para volver al modo local: cerrar el túnel (`Ctrl+C` en la terminal 1) y usar
`docker compose up` de siempre.

---

## Entrar a la base desde la terminal (psql)

**Opción A — dentro de la EC2** (no necesita el túnel):

```powershell
ssh -i certs/llave-aws.pem USUARIO_EC2@IP_EC2
```

y ya adentro:

```bash
sudo -u postgres psql -d NOMBRE_BD
```

(Si Postgres corre en Docker dentro de la EC2, primero `sudo docker ps` para ver
el nombre del contenedor y luego `sudo docker exec -it <contenedor> psql -U USUARIO_BD -d NOMBRE_BD`.)

**Opción B — desde tu máquina, por el túnel** (con la terminal 1 abierta):

```powershell
docker run --rm -it postgres:16 psql -h host.docker.internal -p 5433 -U USUARIO_BD -d NOMBRE_BD
```

Comandos útiles ya dentro de `psql`:

```sql
SELECT current_database(), inet_server_addr();  -- confirmar a qué base estás conectado
\dt                                               -- listar tablas
SELECT id, correo, nombre, rol_id, creado_en FROM usuarios;
\q                                                -- salir
```

---

## Reiniciar la base desde cero

Borra **todos los datos del equipo** en la base de AWS y no se puede deshacer.
Avisen antes de hacerlo.

1. Detener el backend (`Ctrl+C` en la terminal 2, o `docker compose down`).
2. En `psql`:

   ```sql
   DROP TABLE IF EXISTS
     consumo_anonimo, consultas, tokens, auditoria, usuarios, roles, schema_migrations
   CASCADE;
   DROP FUNCTION IF EXISTS set_actualizado_en(), registrar_auditoria_usuario();
   \dt      -- debe decir "Did not find any relations"
   ```

   `schema_migrations` **tiene que** borrarse junto con las demás: si queda,
   `migrate.py` cree que todo ya está aplicado y no vuelve a crear las tablas.
3. Levantar otra vez en modo AWS: las migraciones recrean todo solas.

---

## Qué NO hacer

- ❌ Subir el `.pem`, el `.env` o la clave de la base a Git, a un issue o a un chat público.
- ❌ Poner los datos de AWS en `docker-compose.yml`: esa configuración es la de todos.
- ❌ Usar el modo AWS para programar día a día: se mezclan los datos de prueba
  de todo el equipo.
- ❌ Crear una rama "de AWS": el código es el mismo, solo cambia la configuración.

**Si la llave o una clave se subió por error:** sacarla del repo con
`git rm --cached <archivo>` no alcanza, porque sigue en el historial. Avisen de
inmediato: hay que **generar un nuevo par de llaves** en AWS y cambiar la clave
de la base.

---

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `UNPROTECTED PRIVATE KEY FILE` | Faltan los permisos del paso 2 |
| `Permission denied (publickey)` | Usuario SSH equivocado (`ubuntu` vs `ec2-user`) o llave equivocada |
| SSH se queda colgado | El *security group* no permite el puerto 22 desde tu IP |
| `bind [127.0.0.1]:5433: Address already in use` | Ya hay un túnel abierto, o algo más usa el 5433 |
| `Falta DATABASE_URL_AWS en el .env` | No se hizo el paso 4 |
| `connection refused` en `host.docker.internal:5433` | El túnel no está abierto (terminal 1) |
| `password authentication failed` | Usuario o clave de **Postgres** incorrectos, o clave sin codificar |
| `!reset` no reconocido / error de sintaxis en el YAML | Docker Compose anterior a 2.24.4 |
