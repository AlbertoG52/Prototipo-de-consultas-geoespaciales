# certs/ — conexión a la base de datos de AWS

Esta carpeta guarda el certificado `.pem` que se usa para conectarse **cifrado**
a la base de datos de AWS (RDS). Solo hace falta para el **modo AWS**: demos e
integración. Para el desarrollo diario no se necesita nada de esto.

> **Lo único que se sube a Git de esta carpeta es este README.**
> El `.gitignore` ignora todo lo demás (`certs/*`) y cualquier `*.pem` del repo.

---

## Cuándo se usa cada modo

| Modo | Comando | Base de datos | Para qué |
|---|---|---|---|
| Local (el de siempre) | `docker compose up --build` | Postgres en Docker, uno por persona | Programar y probar |
| AWS | `docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build` | RDS en AWS, compartida | Demos e integración |

**Regla:** el modo AWS se levanta **solo desde `main`**. Al arrancar, el backend
aplica las migraciones pendientes. Si alguien lo levanta desde su rama, una
migración a medio hacer queda aplicada en la base que usa todo el equipo.

---

## Configuración (una vez por persona)

### 1. Poner el certificado en esta carpeta

El archivo debe quedar exactamente en:

```
certs/global-bundle.pem
```

- Es el **certificado de AWS RDS**, no una llave SSH de EC2. Es público: se
  descarga de la documentación de AWS ("Using SSL/TLS to encrypt a connection
  to a DB instance") o lo comparte quien administra la cuenta.
- Si el que tienen tiene otro nombre (por ejemplo `us-east-1-bundle.pem`),
  **renómbrenlo** a `global-bundle.pem` o cambien el nombre en `DATABASE_URL_AWS`.
- Se pasa por un canal privado del equipo, **nunca por el repositorio**.

### 2. Agregar `DATABASE_URL_AWS` al `.env`

En el `.env` de la raíz del proyecto (no en `.env.example`):

```
DATABASE_URL_AWS=postgresql://USUARIO:CLAVE@ENDPOINT.rds.amazonaws.com:5432/NOMBRE_BD?sslmode=verify-full&sslrootcert=/certs/global-bundle.pem
```

| Parte | De dónde sale |
|---|---|
| `USUARIO`, `CLAVE` | Credenciales de la base, las da quien administra AWS |
| `ENDPOINT` | Consola de AWS → RDS → la instancia → *Connectivity & security* → *Endpoint* |
| `NOMBRE_BD` | El nombre de la base dentro de la instancia |
| `/certs/global-bundle.pem` | **No se cambia.** Es la ruta *dentro del contenedor*: `docker-compose.aws.yml` monta esta carpeta en `/certs` |

⚠️ **Si la clave tiene caracteres especiales** (`@ : / ? # & %`), hay que
escribirlos codificados en la URL: `@` → `%40`, `:` → `%3A`, `/` → `%2F`,
`#` → `%23`, `%` → `%25`. Si no, la conexión falla con un error engañoso.

### 3. Permitir tu IP en AWS

El *security group* de la instancia RDS tiene que permitir el puerto **5432**
desde tu IP pública. Lo configura quien administra la cuenta.
Síntoma de que falta: el backend se queda colgado al arrancar y termina en
*timeout*, sin un error claro.

### 4. Tener Docker Compose 2.24.4 o superior

```bash
docker compose version
```

Docker Desktop actualizado ya lo cumple.

---

## Levantar en modo AWS

```bash
git checkout main
git pull
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```

Cómo verificar que está usando AWS y no la base local:

- En `docker compose ps` **no** debe aparecer el contenedor `db`.
- http://localhost:8000/db-check debe responder `"conexion": "ok"`.

Para volver al modo local basta con `docker compose up` de siempre. No hay que
tocar nada más: `DATABASE_URL_AWS` se ignora en modo local.

---

## Qué NO hacer

- ❌ Subir el `.pem`, el `.env` o la clave de la base a Git, a un issue o a un chat público.
- ❌ Poner la URL de AWS en `docker-compose.yml`: esa configuración es la de todos.
- ❌ Usar el modo AWS para programar día a día: se mezclan los datos de prueba
  de todo el equipo.
- ❌ Crear una rama "de AWS": el código es el mismo, solo cambia la configuración.

**Si un `.pem` o una clave se subió por error:** sacarlo del repo con
`git rm --cached <archivo>` no alcanza, porque sigue en el historial. Avisen de
inmediato para **cambiar la clave de la base** en AWS. Si era una llave privada,
hay que generar una nueva.

---

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `Falta DATABASE_URL_AWS en el .env` | No se hizo el paso 2 |
| `root certificate file "/certs/global-bundle.pem" does not exist` | El archivo no está en `certs/` o tiene otro nombre |
| Se queda colgado y da *timeout* | El *security group* no permite tu IP (paso 3) |
| `password authentication failed` | Credenciales incorrectas o clave sin codificar |
| `server certificate does not match host name` | En la URL se usó una IP en vez del *endpoint* de RDS |
| `!reset` no reconocido / error de sintaxis en el YAML | Docker Compose anterior a 2.24.4 (paso 4) |
