# Despliegue en AWS

Configuración de producción en una instancia EC2 con Docker. Esta carpeta vive en la
rama `despliegue` y no modifica el entorno de desarrollo.

| Archivo | Descripción |
|---|---|
| `docker-compose.prod.yml` | Backend y frontend compilado detrás de Caddy |
| `web.Dockerfile` | Compila el frontend y lo sirve con Caddy |
| `Caddyfile` | HTTPS automático; frontend en `/` y API en `/api` |
| `.env.produccion.example` | Plantilla de variables de producción |

```
Usuarios ──HTTPS──► EC2 (Docker)
                     Caddy :443 ─┬─ /      → frontend
                                 └─ /api/* → backend :8000 ──► RDS PostgreSQL
                                                 └─ MCP_URL ──► CR-BioLM
```

- **Base de datos:** Amazon RDS (no hay contenedor de PostgreSQL).
- **CR-BioLM:** externo a la EC2; el backend lo localiza con `MCP_URL`.
- **Dominio:** sin dominio propio se usa `IP-CON-GUIONES.sslip.io`; Caddy obtiene el certificado HTTPS.

> Nunca subir al repositorio la llave `.pem`, `.env.produccion`, contraseñas, la IP
> ni el endpoint de la RDS.

## Ramas

`despliegue` es `main` más esta carpeta. Los cambios se integran siempre de `main`
hacia `despliegue`; en `despliegue` solo se modifican archivos de `despliegue/`.
Las migraciones nuevas se aplican al arrancar el backend.

## Requisitos en AWS

| Recurso | Configuración |
|---|---|
| EC2 | Ubuntu con `git` y `psql` |
| Security group | Puertos 80 y 443 abiertos; 5432, 8000 y 8765 cerrados |
| RDS | Acepta conexiones desde la EC2 |

Si la EC2 se detiene y se vuelve a iniciar, la IP pública cambia: actualizar `DOMINIO`,
`URL_FRONTEND` y `ORIGENES_PERMITIDOS` y volver a levantar.

## 1. Base de datos

Crear un usuario y una base exclusivos de la aplicación (la contraseña de `postgres`
no se guarda en la EC2):

```bash
psql -h ENDPOINT-DE-RDS -p 5432 -U postgres -d postgres
```

```sql
CREATE ROLE flora_app LOGIN PASSWORD 'CONTRASEÑA';
CREATE DATABASE flora_prod OWNER flora_app;
```

Las tablas las crean las migraciones al arrancar el backend.

## 2. Preparar la EC2

```bash
ssh -i "RUTA/LLAVE.pem" ubuntu@IP_PUBLICA
```

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu        # cerrar sesión y volver a entrar
git clone -b despliegue https://github.com/AlbertoG52/Prototipo-de-consultas-geoespaciales.git
```

## 3. Variables de entorno

```bash
cd ~/Prototipo-de-consultas-geoespaciales/despliegue
cp .env.produccion.example .env.produccion
nano .env.produccion
chmod 600 .env.produccion
```

| Variable | Valor |
|---|---|
| `DOMINIO` | IP con guiones + `.sslip.io` (p. ej. `1-2-3-4.sslip.io`) |
| `URL_FRONTEND`, `ORIGENES_PERMITIDOS` | `https://` + `DOMINIO` |
| `DATABASE_URL` | `postgresql://flora_app:CLAVE@ENDPOINT:5432/flora_prod?sslmode=require` |
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CATALOGO`, `MCP_URL` | `demo`, o `crbiolm` con la dirección de CR-BioLM |
| `SMTP_USUARIO`, `SMTP_PASSWORD` | Cuenta de correo para verificación y recuperación |

`.env.produccion` existe solo en la EC2: Git lo ignora y Docker lo lee al arrancar.

## 4. Levantar

```bash
docker compose --env-file .env.produccion -f docker-compose.prod.yml up -d --build
```

Verificación:

```bash
docker compose --env-file .env.produccion -f docker-compose.prod.yml ps
docker compose --env-file .env.produccion -f docker-compose.prod.yml logs -f backend
```

- `https://DOMINIO` abre la aplicación.
- `https://DOMINIO/api/health` responde `{"status":"ok"}`.
- `https://DOMINIO/api/db-check` responde `"conexion": "ok"`.

Primer supermoderador (registrar la cuenta desde el sitio y luego):

```bash
docker compose --env-file .env.produccion -f docker-compose.prod.yml exec backend python cambiar_rol.py CORREO supermoderador
```

## 5. CR-BioLM

### Mediante túnel SSH inverso

Permite usar un servidor CR-BioLM local sin exponer puertos a internet. Solo puede
haber un túnel activo a la vez y el equipo que lo presta debe permanecer encendido.

Una vez, en la EC2:

```bash
echo 'GatewayPorts clientspecified' | sudo tee /etc/ssh/sshd_config.d/tunel-crbiolm.conf
sudo systemctl restart ssh
```

En el equipo que presta CR-BioLM:

1. Levantar CR-BioLM en el puerto 8765 (ver el README principal).
2. Abrir el túnel y mantener la terminal abierta:

   ```bash
   ssh -i "RUTA/LLAVE.pem" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -R 172.17.0.1:8765:localhost:8765 ubuntu@IP_PUBLICA
   ```

3. En `.env.produccion`: `CATALOGO=crbiolm` y `MCP_URL=http://host.docker.internal:8765/mcp`.
4. Reiniciar el backend:

   ```bash
   docker compose --env-file .env.produccion -f docker-compose.prod.yml up -d backend
   ```

5. Comprobar `https://DOMINIO/api/mcp-check`.

Al cerrar el túnel, volver a `CATALOGO=demo` y reiniciar el backend.

### Servidor publicado

Con CR-BioLM accesible en una dirección fija, basta con cambiar `MCP_URL` y reiniciar
el backend. El túnel y la opción `GatewayPorts` dejan de ser necesarios.

## 6. Actualizar

1. Integrar `main` en `despliegue` y hacer push.
2. En la EC2:

   ```bash
   cd ~/Prototipo-de-consultas-geoespaciales && git pull
   cd despliegue
   docker compose --env-file .env.produccion -f docker-compose.prod.yml up -d --build
   ```

## 7. Revertir

| Acción | Comando |
|---|---|
| Detener el sitio | `docker compose --env-file .env.produccion -f docker-compose.prod.yml down` |
| Eliminar contenedores, imágenes y certificados | `... down -v` y `docker system prune -a` |
| Desinstalar Docker | `sudo apt purge -y docker.io docker-compose-v2 && sudo rm -rf /var/lib/docker` |
| Quitar el túnel | `sudo rm /etc/ssh/sshd_config.d/tunel-crbiolm.conf && sudo systemctl restart ssh` |
| Eliminar base y usuario | En `psql` como `postgres`: `DROP DATABASE flora_prod;` y `DROP ROLE flora_app;` |

## Consideraciones

- `/api/docs` es público; puede restringirse en el `Caddyfile`.
- Let's Encrypt limita los certificados por semana: no borrar el volumen `caddy_data` sin necesidad.
- Activar los respaldos automáticos de la RDS si los datos pasan a ser importantes.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `Falta DOMINIO en .env.produccion` | Falta el archivo, la variable o la opción `--env-file` |
| El sitio no abre o no hay HTTPS | `DOMINIO` con otra IP, o puertos 80/443 cerrados |
| `db-check` falla | `DATABASE_URL` incorrecta (caracteres especiales sin codificar, base o usuario inexistente) |
| `permission denied` al crear tablas | La base no pertenece a `flora_app` |
| Error de conexión con CR-BioLM | Túnel cerrado, CR-BioLM apagado o falta `GatewayPorts` |
| `remote port forwarding failed` | Ya hay otro túnel abierto |
| No llegan los correos | Faltan `SMTP_USUARIO`/`SMTP_PASSWORD`; los enlaces aparecen en el log del backend |
