# despliegue/ — el proyecto en la EC2 de AWS

Todo lo de producción vive en esta carpeta, en la rama **`despliegue`**. **No
cambia nada del desarrollo local**: `docker-compose.yml`, los Dockerfiles y el
código siguen igual.

| Archivo | Qué es |
|---|---|
| `docker-compose.prod.yml` | Backend + frontend compilado detrás de Caddy (HTTPS) |
| `web.Dockerfile` | Compila el frontend (`npm run build`) y lo sirve con Caddy |
| `Caddyfile` | HTTPS automático, el frontend en `/` y el backend en `/api` |
| `.env.produccion.example` | Plantilla del `.env` de producción |
| `.gitignore` | Evita subir `.env.produccion` |

```
 Usuarios ──HTTPS──► EC2 (Ubuntu, Docker)
                      Caddy :443 ─┬─ /      → frontend compilado
                                  └─ /api/* → backend :8000 ──► RDS Postgres (flora_prod)
                                                  │
                                                  └─ MCP_URL ──► CR-BioLM
                                                     (hoy: una laptop por túnel SSH;
                                                      después: donde lo publique José)
```

- **Entorno temporal de pruebas:** la EC2 es prestada y queda siempre encendida.
  Todo lo de esta guía se puede revertir (sección 9).
- **Base de datos:** la RDS. Aquí no hay contenedor de Postgres.
- **CR-BioLM:** no corre en la EC2. El backend lo busca en `MCP_URL`; cuando
  José lo publique, solo cambia esa línea.
- **Dirección:** sin dominio propio se usa `IP-CON-GUIONES.sslip.io` (gratis):
  con un nombre, Caddy obtiene solo el certificado HTTPS.

> El repositorio es **público**. Nunca subir la llave `.pem`, `.env.produccion`,
> contraseñas, la IP ni el endpoint de la RDS.

---

## 1. Ramas de Git

```
main ───●───●───●───●───►   (el equipo trabaja aquí, como siempre)
          │           │
          ▼ merge     ▼ merge (cuando se quiera actualizar el sitio)
despliegue ●──(+despliegue/)──●──►   ← la EC2 usa siempre esta rama
```

- La rama `despliegue` es `main` más esta carpeta.
- **El merge va siempre de `main` hacia `despliegue`**, nunca al revés.
- En `despliegue` solo se cambian archivos de `despliegue/`. Lo demás entra por `main`.
- El merge es el momento en que llegan a producción las **migraciones nuevas**
  (el backend las aplica al arrancar): hacerlo con `main` estable.

## 2. Lo que ya está listo en AWS

| Pieza | Estado |
|---|---|
| EC2 | Ubuntu 26.04, t3.medium (2 CPU, 3,7 GB): **no necesita swap**. `git` y `psql` ya instalados; `sudo` sin contraseña |
| Security group de la EC2 | **80 y 443 abiertos**; 8000, 8765 y 5432 cerrados (así debe quedar) |
| RDS | Acepta conexiones desde la EC2. Estaba vacía (sin bases del proyecto) |
| IP pública | No cambia mientras la EC2 siga encendida: **no hace falta Elastic IP** |

Si algún día la EC2 se detiene y se vuelve a iniciar (no al reiniciarla), la IP
cambia: actualizar `DOMINIO`, `URL_FRONTEND` y `ORIGENES_PERMITIDOS` (sección 5)
y volver a levantar.

## 3. Base de datos en la RDS (una vez)

Se usa una base **solo para producción** (`flora_prod`) y un usuario **solo para
la aplicación** (`flora_app`), dueño únicamente de esa base. El usuario maestro
`postgres` queda para administrar a mano y su contraseña **no va en la EC2**: si
el `.env.produccion` se filtrara, solo quedaría expuesta `flora_prod`.

Desde la EC2 (la contraseña de `postgres` la escribe quien administra):

```bash
psql -h ENDPOINT-DE-RDS -p 5432 -U postgres -d postgres
```

Ya en `psql` (la contraseña de `flora_app`: una nueva y larga, distinta a la de `postgres`):

```sql
CREATE ROLE flora_app LOGIN PASSWORD 'CONTRASEÑA-NUEVA-DE-FLORA-APP';
CREATE DATABASE flora_prod OWNER flora_app;
\l
\q
```

Las tablas no se crean a mano: las crean las migraciones al arrancar el backend.

## 4. Preparar la EC2 (una vez)

Entrar desde PowerShell, con la llave `.pem` que les dio AWS:

```powershell
ssh -i "RUTA\A\LA-LLAVE.pem" ubuntu@IP_PUBLICA
```

Ya adentro:

```bash
# Ubuntu tiene un reinicio pendiente por actualizaciones: hacerlo primero
sudo reboot          # esperar ~1 minuto y volver a entrar

# Docker y Compose, desde los repositorios de Ubuntu
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu     # luego salir (exit) y volver a entrar

# El código: la rama despliegue
git clone -b despliegue https://github.com/AlbertoG52/Prototipo-de-consultas-geoespaciales.git
```

## 5. El `.env.produccion` (una vez)

El servidor reconoce las credenciales igual que el `.env` local: el archivo
**existe solo en el disco de la EC2**. Git lo ignora, así que un `git pull` no lo
borra ni lo sube, y Docker lo lee al arrancar (no queda dentro de las imágenes).

```bash
cd ~/Prototipo-de-consultas-geoespaciales/despliegue
cp .env.produccion.example .env.produccion
nano .env.produccion
chmod 600 .env.produccion      # solo el usuario ubuntu puede leerlo
```

| Variable | Valor |
|---|---|
| `DOMINIO` | La IP con guiones: IP `1.2.3.4` → `1-2-3-4.sslip.io` |
| `URL_FRONTEND`, `ORIGENES_PERMITIDOS` | Lo mismo con `https://` delante |
| `DATABASE_URL` | `flora_app`, su contraseña, el endpoint de la RDS, la base `flora_prod` y `?sslmode=require` |
| `SECRET_KEY` | Una nueva: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CATALOGO`, `MCP_URL` | `demo` para empezar; `crbiolm` con el túnel (sección 7) |
| `SMTP_USUARIO`, `SMTP_PASSWORD` | Opcional. Sin ellos, nadie nuevo puede verificar su cuenta (los enlaces salen en el log) |

Dónde vive cada credencial:

| Credencial | Dónde está | Dónde nunca |
|---|---|---|
| Llave `.pem` | Solo en las computadoras del equipo | GitHub, chats públicos |
| Contraseña de `flora_app`, `SECRET_KEY`, SMTP | `.env.produccion`, en la EC2 | GitHub, imágenes de Docker |
| Contraseña de `postgres` | Solo con quien administra la RDS | La EC2, GitHub |

## 6. Levantar

```bash
cd ~/Prototipo-de-consultas-geoespaciales/despliegue
docker compose --env-file .env.produccion -f docker-compose.prod.yml up -d --build
```

La primera vez tarda unos minutos (compila el frontend). Comprobar:

```bash
docker compose --env-file .env.produccion -f docker-compose.prod.yml ps
docker compose --env-file .env.produccion -f docker-compose.prod.yml logs -f backend
```

- `https://IP-CON-GUIONES.sslip.io` abre el chat, con candado.
- `https://IP-CON-GUIONES.sslip.io/api/health` responde `{"status":"ok"}`.
- `https://IP-CON-GUIONES.sslip.io/api/db-check` responde `"conexion": "ok"`.

**El primer supermoderador:** crear la cuenta desde el sitio y luego:

```bash
docker compose --env-file .env.produccion -f docker-compose.prod.yml exec backend python cambiar_rol.py CORREO supermoderador
```

## 7. CR-BioLM

### Mientras sea temporal: túnel SSH inverso

Una persona del equipo **presta su CR-BioLM local** a la EC2. No se abre ningún
puerto a internet: el túnel solo se ve dentro de la EC2. Ya se probó: desde la
EC2 respondió el servidor de José con sus herramientas y datos reales; cada
llamada tarda ~2 s de ida y vuelta, así que las respuestas son algo más lentas
que en local.

- **Basta con uno encendido** para que el sitio funcione para todos.
- **Uno a la vez:** si alguien ya tiene el túnel, el de otra persona falla con
  `remote port forwarding failed`. Se pueden turnar.
- Quien preste el suyo necesita el código del servidor de José, **los mismos
  datos del cliente**, su llave de OpenRouter en el `.env` de su CR-BioLM y la
  llave `.pem`.
- Su computadora debe quedar **encendida y sin suspenderse** mientras preste el servicio.

**Una vez, en la EC2** (para que el túnel escuche en la red de Docker):

```bash
echo 'GatewayPorts clientspecified' | sudo tee /etc/ssh/sshd_config.d/tunel-crbiolm.conf
sudo systemctl restart ssh
```

**Cada vez, en la computadora que presta CR-BioLM:**

1. Levantar CR-BioLM como en desarrollo, desde la raíz del clon con datos:

   ```bash
   python -c "from mpcr_rag.mcp.server import server; server.run(transport='streamable-http', host='0.0.0.0', port=8765)"
   ```

2. En otra terminal, abrir el túnel y dejarla abierta (no muestra nada):

   ```powershell
   ssh -i "RUTA\A\LA-LLAVE.pem" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -R 172.17.0.1:8765:localhost:8765 ubuntu@IP_PUBLICA
   ```

3. En `.env.produccion`: `CATALOGO=crbiolm` y
   `MCP_URL=http://host.docker.internal:8765/mcp`, y reiniciar el backend:

   ```bash
   docker compose --env-file .env.produccion -f docker-compose.prod.yml up -d backend
   ```

4. Comprobar: `https://IP-CON-GUIONES.sslip.io/api/mcp-check` responde
   `"conexion": "ok"` con la lista de herramientas.

Para dejar de prestarlo: `Ctrl+C` en la terminal del túnel. Si nadie más lo
abre, volver a `CATALOGO=demo` y reiniciar el backend, para que el sitio siga
funcionando con datos de ejemplo.

> Antes de instalar Docker en la EC2 no existe la red `172.17.0.1`: para una
> prueba del túnel sin Docker se usa `-R 127.0.0.1:8765:localhost:8765`.

### Cuando José publique CR-BioLM

Cambiar solo `MCP_URL` por su dirección (con `CATALOGO=crbiolm`) y reiniciar el
backend. El túnel y el ajuste `GatewayPorts` dejan de hacer falta (sección 9).

## 8. Actualizar el sitio a una versión nueva

1. En Git (desde una computadora): merge de `main` hacia `despliegue` y push.
2. En la EC2:

   ```bash
   cd ~/Prototipo-de-consultas-geoespaciales
   git pull
   cd despliegue
   docker compose --env-file .env.produccion -f docker-compose.prod.yml up -d --build
   ```

Al arrancar, el backend aplica las migraciones nuevas a `flora_prod`.

## 9. Volver atrás

Todo se puede revertir. Lo único irreversible es **borrar datos reales** o
**subir una credencial a GitHub** (si pasa, hay que cambiar esa credencial).

| Qué | Cómo |
|---|---|
| Detener el sitio | `docker compose --env-file .env.produccion -f docker-compose.prod.yml down` (se vuelve a levantar con `up -d`) |
| Contenedores, imágenes y certificados | `... down -v` y `docker system prune -a` |
| Docker | `sudo apt purge -y docker.io docker-compose-v2 && sudo rm -rf /var/lib/docker` |
| Código en la EC2 | `rm -rf ~/Prototipo-de-consultas-geoespaciales` (guardar antes el `.env.produccion` si hace falta) |
| Ajuste del túnel | `sudo rm /etc/ssh/sshd_config.d/tunel-crbiolm.conf && sudo systemctl restart ssh` |
| Base y usuario (borra los datos) | En `psql` como `postgres`: `DROP DATABASE flora_prod;` y `DROP ROLE flora_app;` |
| Rama | Borrar `despliegue` en Git; `main` nunca se toca |

## A tener en cuenta

- **`/api/docs`** (documentación de la API) queda pública. Para un prototipo
  está bien; se puede cerrar en el `Caddyfile` si hace falta.
- **Let's Encrypt** limita cuántos certificados se piden por semana: no borrar
  el volumen `caddy_data` sin necesidad.
- **Respaldos:** los datos son de prueba; si se vuelven importantes, revisar
  los *automated backups* de la RDS.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `Falta DOMINIO en .env.produccion` | No se creó o no se llenó `.env.produccion`, o falta `--env-file .env.produccion` |
| El sitio no abre o no hay HTTPS | `DOMINIO` con otra IP, o los puertos 80/443 dejaron de estar abiertos en el security group |
| `db-check` falla / el backend se reinicia | `DATABASE_URL` mal (clave con símbolos sin codificar, base o usuario inexistente) |
| `permission denied` al crear tablas | La base no es de `flora_app`: crearla con `OWNER flora_app` (sección 3) |
| Error de conexión con CR-BioLM | Túnel cerrado, CR-BioLM apagado, falta `GatewayPorts`, o `CATALOGO=crbiolm` sin túnel |
| `remote port forwarding failed` | Otra persona ya tiene el túnel abierto |
| Los correos no llegan | Faltan `SMTP_USUARIO`/`SMTP_PASSWORD`; los enlaces salen en `logs backend` |
