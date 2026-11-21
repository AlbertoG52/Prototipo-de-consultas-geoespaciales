# Prototipo de consultas geoespaciales

Agente web que responde, en lenguaje natural, preguntas sobre la flora de Costa Rica: dónde
crece una especie, en qué hábitat vive y cómo es. Cada respuesta combina el Manual de Plantas
de Costa Rica con los registros de presencia de GBIF y, cuando hay datos suficientes, incluye
un mapa de distribución. Los datos de especies provienen de CR-BioLM, que el backend consume
mediante MCP.

| Capa | Tecnologías |
|---|---|
| Frontend | React 19, TypeScript, Vite 6, Tailwind CSS 4, React Router 7 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 |
| Base de datos | PostgreSQL 16 |
| Datos externos | CR-BioLM por MCP (Manual de Plantas, GBIF, mapas, LLM) |
| Infraestructura | Docker Compose |

## Requisitos

- Docker Desktop (o Docker con Docker Compose).
- Para datos reales: el servidor de CR-BioLM (ver "Conexión con CR-BioLM").

## Instalación y arranque

1. Copie el archivo de ejemplo y complete sus valores:

   ```bash
   cp .env.example .env
   ```

2. Levante los servicios:

   ```bash
   docker compose up --build
   ```

   La base de datos arranca y conserva sus datos en un volumen; el backend espera a la
   base, aplica las migraciones pendientes y arranca la API; el frontend arranca en modo
   desarrollo.

3. Cree el primer supermoderador. Toda cuenta nueva se registra con rol `usuario`; para
   asignar otro rol, registre la cuenta desde la aplicación y ejecute:

   ```bash
   docker compose exec backend python cambiar_rol.py <correo> supermoderador
   ```

Si se agrega una dependencia al frontend (cambia `package.json`), actualice el volumen de
`node_modules` con el contenedor levantado:

```bash
docker compose exec frontend npm install
```

### Direcciones

| Servicio | Dirección |
|---|---|
| Aplicación | http://localhost:5173 |
| API y documentación | http://localhost:8000/docs |
| Estado de la API y de la BD | http://localhost:8000/health, http://localhost:8000/db-check |
| Conexión con CR-BioLM | http://localhost:8000/mcp-check |
| PostgreSQL (opcional, para inspección) | localhost:5432 |

### Modo AWS

Para conectar el backend a la base de datos de AWS en lugar de la local:

```bash
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```

Requiere el túnel SSH abierto y `DATABASE_URL_AWS` en el `.env`. Los pasos están en
[`certs/README.md`](certs/README.md).

## Configuración

Todas las variables se definen en el `.env` (ver `.env.example`). Las principales:

| Variable | Uso |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales de la base de datos local. |
| `SECRET_KEY` | Firma de los tokens de sesión. Debe ser larga y aleatoria. |
| `LIMITE_CONSULTAS_ANONIMO` | Consultas diarias del visitante sin cuenta. |
| `MINUTOS_INACTIVIDAD_SESION` | Minutos sin actividad que cierran la sesión (cada usuario puede elegir otro). |
| `INTENTOS_LOGIN_MAXIMOS`, `MINUTOS_BLOQUEO_LOGIN` | Bloqueo temporal tras contraseñas incorrectas seguidas. |
| `SMTP_*`, `URL_FRONTEND` | Envío de correos de verificación y recuperación. Sin SMTP, el enlace se escribe en el log del backend. |
| `CATALOGO` | `demo` (datos de ejemplo) o `crbiolm` (datos reales). |
| `MCP_URL`, `MCP_TIMEOUT_SEGUNDOS`, `MCP_LLAMADAS_SIMULTANEAS` | Conexión con CR-BioLM. |
| `SEGUNDOS_MAXIMOS_CONSULTA` | Tiempo máximo de una consulta. |
| `SEGUNDOS_MAXIMOS_REDACCION_IA` | Tiempo máximo para la respuesta redactada por el LLM. |
| `MINIMO_REGISTROS_MAPA`, `GBIF_REINTENTOS` | Mínimo de registros para el mapa y reintentos ante fallos de GBIF. |
| `SEGUNDOS_RESPUESTA_LENTA` | Umbral para marcar una consulta como lenta. |
| `ADMIN_VE_TEXTO_CONSULTAS` | Si el supermoderador ve el texto de las consultas de cada cuenta. |

## Arquitectura

```
Backend/
  migrations/      esquema de la BD, un archivo SQL por cambio
  app/
    config.py      variables de entorno y límites
    db.py          conexión y sesión de BD por petición
    dominio.py     valores fijos: roles, estados y tipos
    errores.py     errores de negocio
    security.py    contraseñas, tokens, identidad y control de acceso por rol
    main.py        montaje de la API
    models/        mapeo SQLAlchemy de las tablas
    schemas/       entrada y salida (Pydantic)
    routers/       endpoints HTTP
    services/      lógica de negocio (consultas, catálogo, MCP, límites…)
  tests/           pruebas automatizadas
  cambiar_rol.py   cambio de rol desde el servidor
Frontend/src/
  services/api.ts  única salida hacia el backend
  context/         sesión (AuthContext) y conversación (ConsultasContext)
  pages/           vistas
  components/      piezas reutilizables; admin/ para el panel de administración
  config/          marca, textos y leyenda del mapa
  types/           tipos de la API (api.ts se genera desde OpenAPI)
  utils/           lógica sin interfaz: descargas, filtros, fuentes
  index.css        paleta de colores (modo claro y oscuro)
```

Reglas del código:

1. Ninguna vista llama a `fetch` directamente: todo pasa por `services/api.ts`.
2. Los modelos no crean tablas: el esquema es de las migraciones.
3. Ningún componente escribe un color directamente: los colores son variables de
   `src/index.css`. La marca (nombre, logo y colores) se cambia en `config/marca.ts`,
   `public/logo.svg` e `index.css`.
4. Los routers no tienen lógica de negocio: validan la sesión, llaman a un servicio y
   traducen sus errores (`app/errores.py`) a HTTP.
5. Roles, estados y tipos se escriben con los enums de `app/dominio.py`, no como texto suelto.

## Base de datos

El esquema se versiona con migraciones numeradas en `Backend/migrations/`, que el backend
aplica al arrancar. La tabla `schema_migrations` registra las aplicadas. Para cambiar el
esquema, agregue un archivo nuevo con el número siguiente; nunca modifique la base a mano.
Para aplicarlas sin reiniciar:

```bash
docker compose exec backend python migrate.py
```

## Endpoints

| Método | Ruta | Uso | Acceso |
|---|---|---|---|
| POST | `/auth/registro` | Crear cuenta (siempre con rol `usuario`) | Público |
| POST | `/auth/login` | Iniciar sesión | Público |
| POST | `/auth/anonimo` | Entrar sin cuenta | Público |
| POST | `/auth/verificar`, `/auth/reenviar-verificacion` | Verificación de correo | Público |
| POST | `/auth/recuperar`, `/auth/restablecer` | Recuperación de contraseña | Público |
| GET | `/auth/sesion` | Estado de la sesión y consultas restantes | Cualquier sesión |
| POST | `/auth/renovar`, `/auth/logout` | Renovar o cerrar la sesión | Cualquier sesión |
| POST | `/consultas` | Enviar una consulta | Cualquier sesión |
| GET | `/conversaciones`, `/conversaciones/{id}` | Historial de conversaciones | Cuenta registrada (solo las propias) |
| GET | `/especies?q=`, `/especies/{id}`, `/especies/{id}/mapa` | Sugerencias, ficha y mapa | Cualquier sesión |
| PATCH/POST | `/perfil`, `/perfil/password`, `/perfil/inactividad` | Nombre, contraseña e inactividad | Cuenta registrada |
| GET/PATCH | `/perfil/preferencias` | Mapa y fuentes en las respuestas | Moderador y supermoderador |
| GET/PATCH | `/admin/usuarios…` | Usuarios, rol, estado e historial de uso | Supermoderador |
| GET/PATCH | `/admin/roles…` | Límite y periodo de cada rol | Supermoderador |
| GET/PUT | `/admin/permisos-consulta` | Tipos de consulta por rol | Supermoderador |
| GET/PUT | `/admin/preferencias-respuesta` | Mapa y fuentes por defecto | Supermoderador |
| GET | `/admin/estadisticas…`, `/admin/uso-por-rol` | Estadísticas de uso | Supermoderador |
| GET | `/admin/auditoria`, `/admin/tiempos` | Auditoría y tiempos de respuesta | Supermoderador |

El rol se valida en el servidor en cada petición (`requiere_rol` en `security.py`): sin
cuenta responde 401 y con otro rol, 403. Todo lo que esté bajo `/admin` queda restringido al
supermoderador.

## Procesamiento de una consulta

`POST /consultas` recorre estas etapas:

1. **Validación del texto**: máximo 500 caracteres, sanitización y limpieza de emojis,
   espacios y signos repetidos.
2. **Límite de consultas**: se cuentan las resueltas del periodo del rol (día, semana o mes,
   desde las 00:00 de Costa Rica). Si se alcanzó, responde 429 con la fecha de reinicio.
3. **Preprocesamiento**: un saludo, un pedido de ayuda, un texto en otro idioma o sin sentido
   recibe una orientación con ejemplos, sin llamar a CR-BioLM.
4. **Permisos por tipo**: se verifica que el rol pueda hacer ese tipo de pregunta
   (distribución, hábitat, descripción o general).
5. **Identificación de la especie**: nombre científico, corrección de errores ortográficos,
   nombre común, sinónimo o género. Si hay varias candidatas, la consulta queda ambigua y el
   usuario elige.
6. **Recuperación**: ficha del Manual, fragmento relevante, registros de GBIF y mapa,
   validados contra la especie identificada. Si la consulta menciona una región o vertiente,
   los registros se filtran por esa zona.
7. **Redacción**: el LLM de CR-BioLM redacta la respuesta con citas del Manual; si falla o
   tarda demasiado, se usa el texto del Manual.
8. **Registro**: la consulta se guarda en la conversación (solo cuentas registradas) y su
   tiempo e intención en `tiempos_respuesta`.

La respuesta tiene uno de cuatro estados: `resuelta`, `ambigua`, `sin_coincidencias` u
`orientacion`. Solo `resuelta` cuenta para el límite. Si la consulta supera
`SEGUNDOS_MAXIMOS_CONSULTA`, responde 504 y no cuenta.

## Conexión con CR-BioLM

El backend usa CR-BioLM únicamente a través de su servidor MCP. La única pieza que se
comunica con él es `Backend/app/services/mcp_cliente.py`:

```python
from app.services import mcp_cliente

sobre = mcp_cliente.llamar("get_species", name="Quercus costaricensis")
sobre.valor        # los datos
sobre.cita         # "Manual de Plantas de Costa Rica, Tomo V, p. 779"
sobre.fuente       # "MPCR", "GBIF", "MPCR+GBIF"...
sobre.advertencia  # aviso que se muestra junto al dato, si lo hay
```

Si algo falla, lanza una subclase de `ErrorMCP` (`MCPNoDisponible`, `MCPTiempoAgotado`,
`MCPErrorHerramienta`, `MCPRespuestaInvalida`).

### Levantar CR-BioLM en desarrollo

CR-BioLM corre fuera de Docker, en la máquina anfitriona, porque necesita los datos del
cliente (`data_raw/` y `mpcr_rag/data/` en la raíz de su clon). Desde esa raíz, ejecute:

```bash
python -c "from mpcr_rag.mcp.server import server; server.run(transport='streamable-http', host='0.0.0.0', port=8765)"
```

- `host='0.0.0.0'` es obligatorio: si escucha solo en 127.0.0.1, rechaza las peticiones del
  contenedor (HTTP 421). Si Windows pregunta por el firewall, permita solo redes privadas.
- Defina `CATALOGO=crbiolm` en el `.env` del proyecto y compruebe la conexión en
  http://localhost:8000/mcp-check.
- La respuesta redactada necesita una llave de OpenRouter en el `.env` **de CR-BioLM**:

  ```
  OPENROUTER_API_KEY=sk-or-v1-...
  MPCR_ENRICH_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
  ```

  Los modelos gratuitos cambian con el tiempo; la guía de hosting de CR-BioLM indica cómo
  listar los disponibles. No elimine `MPCR_ENRICH_MODEL`: sin ella CR-BioLM usa un modelo de
  pago. Sin llave, el backend responde con el texto del Manual.
- Los registros de GBIF se guardan en CR-BioLM y se actualizan cuando superan
  `MPCR_GBIF_CACHE_MAX_DAYS` días (en el `.env` de CR-BioLM; 0 = nunca). Para actualizarlos
  de antemano, por ejemplo con una tarea programada:

  ```bash
  python -m mpcr_rag.scripts.refresh_gbif            # los vencidos
  python -m mpcr_rag.scripts.refresh_gbif --status   # estado de la actualización
  ```

### Nombres comunes y sinónimos

Se precargan en la base de CR-BioLM (contenedor `mpcr-pg`). Desde la raíz de CR-BioLM, con
su entorno virtual activado:

```bash
python -m mpcr_rag.evidence.vernacular fetch --pilot --expert   # nombres comunes
python -m mpcr_rag.evidence.synonyms fetch                      # sinónimos (10-20 min)
python -m mpcr_rag.evidence.synonyms report                     # revisión de la carga
```

Sin estas tablas, el agente reconoce solo nombres científicos. Estos datos pertenecen al
cliente y no se suben a ningún repositorio.

### Producción

CR-BioLM se agrega como un servicio más de Docker, con los datos del cliente montados como
volumen (nunca dentro de la imagen ni del repositorio). `MCP_URL` pasa a ser, por ejemplo,
`http://crbiolm:8765/mcp`, y ese servicio no se publica hacia Internet.

`requirements.txt` fija `mcp==1.12.4`: la serie 2.x exige `pydantic>=2.12`. El cliente 1.12.4
es compatible con el servidor 2.x de CR-BioLM.

## Pruebas y calidad

```bash
docker compose exec backend python -m pytest tests -q
```

Las pruebas usan el catálogo de demostración y no necesitan CR-BioLM: las del adaptador MCP
levantan un servidor falso. Las que pasan por la API usan la base de datos y borran lo que
crean.

| Revisión | Backend | Frontend |
|---|---|---|
| Estilo y errores probables | `ruff check .` | `npm run lint` |
| Formato | `ruff format .` | — |
| Tipos | `mypy` | `npm run typecheck` |

Los tipos del frontend (`src/types/api.ts`) se generan desde el contrato OpenAPI del backend.
Si cambia un esquema de Pydantic, regenérelos con el backend levantado:

```bash
docker compose exec frontend npm run tipos
```

## Seguridad

- Los contenedores corren sin root y las credenciales van en el `.env`, fuera de Git.
- Las contraseñas se guardan con hash bcrypt. `bcrypt` está fijado en 4.0.1 porque
  `passlib` 1.7.4 no es compatible con versiones posteriores.
- El inicio de sesión responde igual ante un correo inexistente y una contraseña incorrecta.
  Tras varios intentos fallidos la cuenta se bloquea temporalmente (423).
- Los enlaces de verificación (24 horas) y de recuperación (30 minutos) son de un solo uso;
  en la base se guarda solo su hash.
- Las reglas de contraseña y la sanitización de entradas se validan en el servidor.
- La auditoría de acciones administrativas no se puede modificar.
