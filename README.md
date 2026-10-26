# Prototipo de consultas geoespaciales

Stack: **Backend** Python/FastAPI · **Frontend** TypeScript/React (Vite) · **BD** PostgreSQL.
Todo corre en Docker.

## Requisitos
- Docker Desktop (o Docker + Docker Compose).

## Arranque (una sola vez)
```bash
cp .env.example .env      # y editá las claves (solo si no ha creado un .env)
docker compose up --build
```

Al levantar:
- La base de datos arranca y persiste sus datos en un volumen.
- El backend espera a la BD, aplica las migraciones pendientes y arranca la API.
- El frontend arranca en modo desarrollo.

Cuando alguien agrega una dependencia al frontend (cambia `package.json`), las
`node_modules` del contenedor viven en un volumen aparte y no se actualizan
solas. Con el contenedor levantado:
```bash
docker compose exec frontend npm install
```

## URLs
- Frontend: http://localhost:5173
- API:      http://localhost:8000/health  y  http://localhost:8000/db-check
- CR-BioLM: http://localhost:8000/mcp-check (lista las herramientas si la conexión MCP funciona)
- API docs: http://localhost:8000/docs
- Postgres: localhost:5432 (para inspeccionar con pgAdmin/DBeaver, opcional)

## Modo AWS (demos e integración)
Por defecto todo corre local. Para conectar el backend a la base de datos de AWS:
```bash
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```
Requiere el túnel SSH abierto con la llave `.pem` y `DATABASE_URL_AWS` en el `.env`. Pasos completos en [`certs/README.md`](certs/README.md).

---

## Arquitectura

```
Backend/
  migrations/      esquema de la BD, un archivo por cambio
  app/
    config.py      variables de entorno y límites
    db.py          engine, sesión por petición
    dominio.py     valores fijos: roles, estados de cuenta y de consulta, tipos de sesión
    errores.py     errores de negocio (los lanzan los servicios)
    tiempo.py      ahora(): la hora actual en UTC
    security.py    hash de contraseñas, tokens, identidad de la petición
    main.py        montaje de la API
    models/        mapeo SQLAlchemy de las tablas que crean las migraciones
    schemas/       entrada y salida (Pydantic)
    routers/       endpoints HTTP: reciben la petición y llaman a un servicio
    services/      lógica de negocio (consultas, autenticación, catálogo, MCP…)
  tests/           pruebas
  pyproject.toml   configuración de ruff y mypy
  exportar_openapi.py  contrato de la API para generar los tipos del frontend

Frontend/src/
  types/           tipos compartidos con la API (api.ts se genera, ver "Calidad del código")
  services/api.ts  única puerta de salida hacia el backend
  context/         AuthContext (sesión) y ConsultasContext (conversación)
  pages/           vistas
  components/      piezas reutilizables (Logo, TarjetaRespuesta, Mapa, Formulario…)
    admin/         piezas del panel de administración: usuarios (RR_70 a RR_76),
                   tipos de consulta por rol (RR_77), estadísticas (RR_78) y
                   respuestas (RR_80)
  hooks/           hooks de React sin interfaz (useRecargaAutomatica, RR_78)
  config/marca.ts  nombre, subtítulo y logo de la aplicación
  config/textos.ts textos y formatos repetidos (idioma de fechas, etiquetas de registros)
  utils/           lógica sin interfaz: descargas, filtro de elevación, mapa de la
                   especie (mapa.ts, RR_54) y fuentes y citas (fuentes.ts, RR_49-51)
  index.css        paleta de colores (modo claro y oscuro)
  routes.tsx       enrutamiento
Frontend/public/
  logo.svg         archivo del logo
```

Reglas que conviene mantener:

1. **Ninguna vista llama a `fetch` directamente.** Todo pasa por `services/api.ts`,
   para que el manejo del token y de los errores viva en un solo lugar.
2. **Los modelos no crean tablas.** `db.py` no llama a `create_all()`. El esquema
   es de las migraciones; los modelos solo lo mapean.
3. **Ningún componente escribe un color directamente.** Los colores se definen
   una sola vez en `Frontend/src/index.css` (bloque `@theme`, con su versión
   oscura en `[data-tema="oscuro"]`) y los componentes usan la variable:
   `style={{ color: "var(--color-texto)" }}`. El nombre y el logo salen de
   `config/marca.ts` y `public/logo.svg`. Así, la marca del cliente (logo,
   nombre, colores) se cambia en esos tres archivos. Los íconos vienen de
   `lucide-react`. Las fuentes también son variables (`var(--font-serif)`,
   `var(--font-mono)`, `var(--fuente-app)`).
4. **Los routers no tienen lógica de negocio.** Un endpoint valida la sesión,
   llama a una función de `services/` y devuelve lo que esta responde. Los
   servicios no saben de HTTP: si una regla no se cumple lanzan un error de
   `app/errores.py` (`NoEncontrado`, `LimiteAlcanzado`…) y el router lo
   convierte en la respuesta HTTP con `with errores_http():`.
5. **Ningún rol, estado o tipo de sesión se escribe como texto suelto.** Se usa
   el enum de `app/dominio.py` (`NombreRol.MODERADOR`, `EstadoConsulta.AMBIGUA`…).
   Un error de tipeo así lo detecta mypy en lugar de fallar en producción.

### La sesión siempre existe

Root es la primera vista y no está protegida (RR_00_11). Si no hay token, el
frontend pide uno anónimo y la persona entra directo al agente. Iniciar sesión
es opcional y sirve para dos cosas: conservar el historial y tener más consultas
al día. Cerrar sesión no deja a nadie fuera, devuelve a la sesión anónima.

| | Visitante | Usuario registrado |
|---|---|---|
| Consultas | 5 por día (`LIMITE_CONSULTAS_ANONIMO`) | las de su rol: 20 por día por defecto (`roles.limite_consultas` y `roles.periodo_consultas`, ver RR_62 a RR_66) |
| Historial | en memoria, se pierde al recargar | conversaciones guardadas (`conversaciones` y `consultas`) |
| Qué se guarda de él | solo un contador diario | correo, consultas y respuestas |

---

## Esquema de la BD

Cada cambio a la base es un archivo SQL numerado en `Backend/migrations/`:

| Archivo | Qué hace |
|---|---|
| `001_crear_tabla_roles.sql` | roles del sistema |
| `002_crear_tabla_usuarios.sql` | usuarios y autenticación |
| `003_auditoria_y_triggers.sql` | auditoría y triggers |
| `004_crear_tabla_consultas.sql` | registro de consultas |
| `005_crear_tabla_tokens.sql` | tokens de verificación y recuperación |
| `006_control_intentos_login.sql` | intentos fallidos y bloqueo |
| `007_preferencias_moderador.sql` | preferencias de respuesta |
| `008_nombre_usuario.sql` | columna `nombre`, que pide la vista de registro |
| `009_sesion_en_consultas.sql` | `sesion_id` y `respuesta`, para RR_09 |
| `010_consumo_anonimo.sql` | contador diario del visitante, para RR_00_11 |
| `011_auditoria_actor_inmutable.sql` | quién hizo cada cambio y auditoría inmutable, para RR_00_09 |
| `012_conversaciones.sql` | historial por conversaciones y los tres estados de una consulta, para RR_09 y RR_17 |
| `013_inactividad_sesion.sql` | minutos de inactividad elegidos por cada usuario, para RR_00_04 |
| `014_verificar_cuentas_existentes.sql` | marca como verificadas las cuentas creadas antes de RR_00_07 |
| `015_tiempos_respuesta.sql` | tiempo de respuesta de cada consulta, para RR_57 |
| `016_consultas_de_orientacion.sql` | estado `orientacion` y columna `motivo` (saludo, ayuda, idioma…), para RR_22, RR_32, RR_37 y RR_40 |
| `017_intencion_de_consulta.sql` | intención de cada consulta en `tiempos_respuesta`, para RR_33 (y RR_29 criterio 3) |
| `018_preferencias_de_respuesta.sql` | comportamiento por defecto de mapa y fuentes (`configuracion_respuestas`) y preferencias del moderador con NULL = "la del sistema", para RR_67, RR_68, RR_79 y RR_80 |
| `019_permisos_tipo_consulta.sql` | tipos de consulta permitidos por rol (`permisos_tipo_consulta`), motivo `tipo_no_permitido` y su registro en la auditoría, para RR_77 |
| `020_limites_por_rol.sql` | periodo del límite de cada rol (`periodo_consultas`), límites válidos y auditoría de sus cambios, para RR_63 y RR_64 |

Para agregar un cambio:
1. Se crea un archivo nuevo, p.ej. `011_....sql`.
2. Se guarda y se sube al repositorio de git.
3. Se ejecuta `git pull` y, al levantar Docker (o con `docker compose exec backend python migrate.py`),
   se realizan los cambios solo si aplica.

Regla: **ningún cambio a la BD se hace a mano; todo va en una migración versionada en Git.**

---

## Endpoints

| Método | Ruta | Para qué | Quién puede usarlo |
|---|---|---|---|
| POST | `/auth/registro` | crear cuenta; siempre con rol `usuario` (RR_61) | público |
| POST | `/auth/login` | iniciar sesión | público |
| POST | `/auth/anonimo` | entrar sin cuenta | público |
| POST | `/auth/verificar` | verificar el correo con el token del enlace (RR_00_07) | público |
| POST | `/auth/reenviar-verificacion` | enviar un enlace de verificación nuevo (RR_00_07) | público |
| POST | `/auth/recuperar` | enviar el enlace para cambiar la contraseña olvidada (RR_00_06) | público |
| POST | `/auth/restablecer` | guardar la contraseña nueva con el token del enlace (RR_00_06) | público |
| POST | `/auth/logout` | cerrar la sesión activa | cualquier sesión |
| GET | `/auth/sesion` | quién soy y cuántas consultas me quedan | cualquier sesión |
| POST | `/consultas` | enviar una consulta | cualquier sesión |
| GET | `/conversaciones` | conversaciones de la cuenta para la barra lateral (últimas 50) | solo cuentas registradas |
| GET | `/conversaciones/{id}` | una conversación completa, para reabrirla | solo el dueño (otra persona recibe 404) |
| GET | `/especies?q=` | sugerencias de nombres entre las especies ya consultadas por cuentas registradas (RR_16) | cualquier sesión |
| GET | `/especies/{id}` | ficha completa de la especie (RR_20) | cualquier sesión |
| PATCH | `/perfil` | cambiar el nombre de la cuenta | solo cuentas registradas |
| POST | `/perfil/password` | cambiar la contraseña (pide la actual) | solo cuentas registradas |
| GET | `/perfil/preferencias` | si mis respuestas incluyen el mapa y las fuentes, y la del sistema (RR_67, RR_68, RR_79) | moderador y supermoderador |
| PATCH | `/perfil/preferencias` | activar o desactivar el mapa o las fuentes; `null` vuelve a la del sistema (RR_67, RR_68) | moderador y supermoderador |
| GET | `/admin/usuarios` | usuarios registrados | supermoderador |
| GET | `/admin/usuarios/{id}/consultas` | historial de uso de una cuenta, por páginas (RR_76) | supermoderador |
| GET | `/admin/uso-por-rol` | cuentas y consultas guardadas de cada rol (RR_76) | supermoderador |
| GET | `/admin/roles` | límite de consultas y periodo de cada rol (RR_63) | supermoderador |
| PATCH | `/admin/roles/{rol}` | definir el límite y el periodo de un rol (RR_63, RR_64); 400 si rompe la regla entre roles | supermoderador |
| GET | `/admin/estadisticas?periodo=` | total de consultas por rol (con visitantes), por día y por tipo; `periodo` = `hoy`, `ultimos_7_dias`, `ultimos_30_dias` o `todo` (por defecto) (RR_78) | supermoderador |
| GET | `/admin/estadisticas/resumen` | cifras de las tarjetas del panel: cuentas, consultas de hoy, ayer y 30 días, tasa de éxito (RR_78) | supermoderador |
| PATCH | `/admin/usuarios/{id}/estado` | activar o desactivar (no a sí mismo: 409) | supermoderador |
| PATCH | `/admin/usuarios/{id}/rol` | cambiar el rol (no a sí mismo: 409) | supermoderador |
| GET | `/admin/auditoria` | registro de acciones administrativas (RR_00_09) | supermoderador |
| GET | `/admin/tiempos` | tiempos de respuesta de las consultas; `?solo_lentas=true` filtra las lentas (RR_57); intención de cada una y conteo por intención (RR_33) | supermoderador |
| GET | `/admin/preferencias-respuesta` | comportamiento por defecto de mapa y fuentes (RR_80) | supermoderador |
| PUT | `/admin/preferencias-respuesta` | cambiarlo; aplica a todos los que no tienen preferencia propia (RR_80) | supermoderador |
| GET | `/admin/permisos-consulta` | tipos de consulta que puede hacer cada rol (RR_77) | supermoderador |
| PUT | `/admin/permisos-consulta` | cambiarlos para los roles enviados; queda en la auditoría (RR_77) | supermoderador |

### Control de acceso por rol

- La validación se hace en el servidor con la dependencia `requiere_rol(...)`
  de `security.py`. Sin cuenta responde **401**; con cuenta y otro rol, **403**.
- El router `/admin` la declara a nivel de router: cualquier endpoint nuevo bajo
  `/admin` queda restringido al supermoderador. `tests/test_roles.py` falla si
  se quita.
- El rol se lee de la BD en cada petición, no del token: un cambio de rol aplica
  de inmediato.
- En el frontend, `RequiereRol` (`routes.tsx`) solo evita mostrar la vista;
  no es la barrera de seguridad.

El texto de las consultas en el historial de uso (RR_76) se entrega solo si
`ADMIN_VE_TEXTO_CONSULTAS=true` (por defecto, en el `.env`); con `false` el
supermoderador ve cuándo consultó cada cuenta, con qué resultado y de qué
especie, pero no lo que escribió.

El registro siempre crea cuentas con rol `usuario` (RR_61): si la petición trae
un campo de rol (`rol`, `rol_id`, `role`…) o cualquier otro campo de más,
responde **422** y no crea la cuenta. Para asignar otro rol:

```bash
docker compose exec backend python cambiar_rol.py <correo> supermoderador
```

`POST /consultas` devuelve uno de cuatro estados:

- `resuelta` — trae `respuesta`; es la única que descuenta del límite diario.
- `ambigua` — trae `candidatos`. El frontend muestra las opciones y reenvía la
  misma consulta con `especie_id` (RR_17). Desambiguar no cuesta una consulta.
- `sin_coincidencias` — no se reconoció ninguna especie.
- `orientacion` — no era una consulta (saludo, ayuda, otro idioma…) o es de un
  tipo que su rol no tiene; trae `motivo`, `mensaje` y `ejemplos`. Ver
  "Mensajes que no son una consulta" y "Tipos de consulta por rol".

Con cuenta, los cuatro estados se guardan dentro de una conversación (RR_09):
`POST /consultas` recibe `conversacion_id` para seguir una conversación, o crea
una nueva si no viene. Una consulta `ambigua` queda **pendiente**: al reabrir la
conversación se pueden elegir sus opciones, y se resuelve enviando
`consulta_id` + `especie_id`. Se actualiza esa misma consulta, así que se cobra
una sola vez y cuenta el día en que se resuelve. Del visitante no se guarda nada.

### Tiempo máximo de una consulta (RR_38)

Cada consulta tiene `SEGUNDOS_MAXIMOS_CONSULTA` segundos (120 por defecto, en el
`.env`) desde que llega al backend hasta que la respuesta está lista, incluidas
todas las llamadas a CR-BioLM. Una llamada MCP nunca dura más de lo que le queda
a la consulta. Si se supera:

- `POST /consultas` responde **504** con un mensaje para el usuario, y la
  consulta **no se guarda ni se descuenta** del límite diario.
- El chat muestra el mensaje con el botón "Reintentar consulta".
- El backend deja en el log qué consulta se cortó y en qué paso.

El frontend conoce el límite por `GET /auth/sesion` (`segundos_maximos_consulta`)
y deja de esperar 10 s después, por si la respuesta del servidor nunca llega.

### El texto de la consulta (RR_21, RR_34, RR_35)

Antes de procesarse, el texto de `POST /consultas` pasa por el esquema
(`schemas/consulta.py`), en este orden:

1. **RR_34 — largo máximo**: `LONGITUD_MAXIMA_CONSULTA` (500 caracteres, en
   `config.py`). Una más larga responde **422** con un mensaje en español que
   dice cuántos caracteres tiene y cuál es el máximo. El chat lo recibe en
   `GET /auth/sesion` (`longitud_maxima_consulta`): muestra un contador desde el
   80 % del límite y, si se pasa, un aviso y no deja enviar. No corta lo que se
   pega.
2. **RR_00_08 — sanitización** (`sanitizar_texto`).
3. **RR_21 — limpieza** (`limpiar_consulta` en `sanitizacion.py`): quita
   emojis y símbolos decorativos, espacios y saltos de línea repetidos, espacios
   junto a los signos y signos repetidos (`"¿¿ dónde  crece ??"` → `"¿dónde
   crece?"`). Conserva mayúsculas, tildes, números y signos como `>`. Si no
   queda nada, la consulta se rechaza como vacía. El texto limpio es el que se
   guarda y se procesa.

**RR_35 — acentos y mayúsculas**: toda búsqueda de especies compara con
`normalizar` (minúsculas y sin tildes), sobre una copia: el texto guardado y
mostrado no cambia. El catálogo de CR-BioLM quita además las tildes de los
nombres científicos antes de buscarlos (`"Quércus"` encuentra *Quercus*).

**RR_23 — errores ortográficos**: si la consulta no trae ningún nombre científico
exacto, `CatalogoCRBioLM` corrige los que tienen hasta `LETRAS_MAXIMAS_CORRECCION`
letras mal escritas (2, en `config.py`) contra el catálogo completo de CR-BioLM
(`search_species`, pedido una sola vez) y vuelve a buscar
(`services/correccion.py`). Solo corrige si hay un único nombre así de cercano.
El texto guardado y mostrado no cambia y no se avisa al usuario; el Manual y el
LLM reciben la pregunta con el nombre corregido.

**RR_25 — nombres comunes**: si no trae ningún nombre científico (ni corregido),
`CatalogoCRBioLM` le pregunta a CR-BioLM (`resolve_common_name`) por las frases
de la consulta que podrían ser un nombre común, de la más larga a la más corta
(`services/nombres_comunes.py`, a lo sumo `NOMBRES_COMUNES_FRASES_MAXIMAS`).
CR-BioLM ya compara sin tildes ni mayúsculas; si una frase no está, se prueba en
singular. Si CR-BioLM elige una especie (`unique` o `preferred`), se responde
con ella y la respuesta lo avisa ("Por «ceiba» se entendió *Ceiba pentandra*…");
si son varias (`ambiguous`), se ofrecen como en RR_17. El Manual y el LLM
reciben la pregunta con el nombre científico al lado del común. Requiere la
tabla de nombres comunes de CR-BioLM (`python -m mpcr_rag.evidence.vernacular
fetch`); sin ella, no se reconocen nombres comunes.

**RR_28 — ambigüedad**: si, aun corregida, la consulta no trae ningún nombre
científico pero sí un género del Manual con dos o más especies ("¿Dónde crece
Quercus?"), se ofrecen sus primeras `GENERO_OPCIONES_MAXIMAS` especies en orden
alfabético (5, en `config.py`) con el estado `ambigua` de RR_17, y el mensaje
pide elegir una o escribir un nombre más específico. Un género con una sola
especie no se ofrece. Al elegir, el Manual y el LLM reciben la pregunta con la
especie elegida en lugar del género.

**RR_36 — varias especies**: si la consulta nombra varias especies ("Quercus
costaricensis y Quercus oleoides"), sigue llegando como `ambigua` con todas. El
frontend lo distingue de un género (RR_28) porque cada opción está escrita en la
consulta (`utils/especies.ts`) y agrega el botón **Buscar todas**: cada especie se
busca como si se eligiera, una tras otra (el LLM de CR-BioLM falla con dos
preguntas a la vez; `BUSQUEDAS_SIMULTANEAS` en `ConsultasContext.tsx`), y cada una
consume una consulta (si no alcanzan para todas, se avisa y no se busca ninguna).
Cada búsqueda le manda a CR-BioLM solo su parte de la pregunta, así el Manual, el
LLM y la zona (RR_39) son los de esa especie.

**RR_39 — región o zona**: si la consulta menciona una región botánica del Manual
("Cordillera de Talamanca", "Talamanca", "Golfito"…) o una vertiente ("Caribe",
"Pacífico"), la lista de registros y su conteo son solo los de esa zona
(`services/regiones.py`, con el vocabulario de `get_vocabulary`, pedido una sola
vez). Una palabra que está en varias regiones las incluye todas. El mapa sigue
siendo el nacional (las herramientas de mapas de CR-BioLM no reciben una región)
y se decide con el total del país. Sin zona, o con una provincia, no se filtra.

### Mensajes que no son una consulta (RR_22, RR_30, RR_32, RR_37, RR_40)

`services/preprocesamiento.py` revisa el mensaje **antes de buscar especies**
(después del límite diario: con el límite alcanzado se avisa eso). Si no es una
consulta, `POST /consultas` responde con el estado **`orientacion`**, un `motivo`,
un `mensaje` para el usuario y `ejemplos` de consultas válidas, sin llamar a
CR-BioLM. En orden:

| Motivo | Cuándo | Ejemplo |
|---|---|---|
| `sin_sentido` (RR_32) | sin letras, o ninguna palabra pronunciable (sin vocales o con 5 consonantes seguidas) | "asdfgh", "123" |
| `idioma` (RR_22) | claramente inglés: 2+ palabras típicas del inglés y más que del español; ante la duda sigue (los nombres científicos no cuentan) | "Where does Quercus costaricensis grow?" |
| `ayuda` (RR_40) | una frase de ayuda y nada más que cortesía o palabras sobre el agente y sus fuentes | "¿Qué puedo hacer con el manual de plantas?" |
| `saludo` (RR_37) | solo cortesía | "hola", "¿qué tal todo por allá?" |
| `fuera_de_tema` (RR_37) | **después** de buscar: ninguna especie y ninguna palabra sobre plantas, geografía o descripción | "¿Quién ganó el mundial?" |
| `fuera_de_tema` (RR_30) | **después** de buscar: ninguna especie y nombra otro país o continente sin mencionar Costa Rica ni un lugar del país | "¿Dónde crece el baobab en África?" |

"¿Para qué sirve la guaria morada?" o "Hola, ¿dónde crece Quercus…?" siguen
siendo consultas: sobra el nombre de la planta. El mensaje de fuera de tema
sugiere el nombre científico, porque CR-BioLM todavía no reconoce nombres
comunes (RR_25).

RR_30 (`fuera_de_costa_rica`) usa el mismo motivo y mensaje que RR_37. Con una
especie reconocida no aplica: "¿Crece Quercus costaricensis en Panamá?" se
responde con los datos de Costa Rica. Una planta que no está en el Manual sigue
siendo `sin_coincidencias`. La lista de lugares deja fuera los que también son
nombres comunes de plantas en Costa Rica (chile, china, india, jamaica, brasil,
guinea).

Una orientación **no descuenta del límite**. De una cuenta registrada se guarda
en su conversación (tabla 016, con `motivo`), se ve en el historial de uso del
panel (RR_76) y **no** suma en el uso por rol. Los ejemplos
(`EJEMPLOS_DE_CONSULTA`, con nombre científico) no se guardan: al reabrir la
conversación se muestran los actuales. En el chat, tocar un ejemplo lo copia al
campo de texto.

### Tipos de consulta por rol (RR_77)

El supermoderador decide en Administración → Roles y permisos qué tipos de
pregunta (`distribucion`, `habitat`, `descripcion`, `general`, los de RR_29)
puede hacer el visitante, el usuario y el moderador. El supermoderador siempre
puede todos. Se guarda en `permisos_tipo_consulta` (019); al inicio todo está
permitido. La lógica está en `services/permisos.py`.

- `POST /consultas` revisa el tipo **antes de buscar especies** (no se llama a
  CR-BioLM ni se muestran candidatas) y otra vez con el tipo de la respuesta,
  que puede precisarse con el vocabulario de CR-BioLM.
- Si no está permitido responde `orientacion` con el motivo
  `tipo_no_permitido` y un mensaje con los tipos que sí tiene ("Tu rol
  (usuario) no tiene habilitadas las consultas de descripción. Puedes preguntar
  por: …"). No descuenta del límite. Los ejemplos que se sugieren, en esta y en
  cualquier orientación, son solo de tipos permitidos.
- Una consulta ambigua pendiente cuyo tipo dejó de estar permitido responde
  **403** al elegir la especie y sigue pendiente.
- Cada cambio de permiso queda en la auditoría (`cambio_permiso`, con quién lo
  hizo), por un trigger de la 019.
- Solo aplica al chat: la ficha de especie (`GET /especies/{id}`) se ve completa.

### Estadísticas de uso (RR_78)

Administración → Estadísticas muestra el **total de consultas** del periodo
elegido (Hoy, Últimos 7 días, Últimos 30 días o Todo), **por rol**, por día
(últimos 7) y por tipo de pregunta. Las tarjetas de arriba del panel (cuentas,
consultas de hoy y de 30 días, tasa de éxito) salen de los mismos conteos. La
lógica está en `services/estadisticas.py`; no hay nada precalculado.

- **Qué cuenta** (misma regla que el uso por rol de RR_76): de las cuentas, sus
  consultas guardadas resueltas, ambiguas y sin coincidencias, no las
  orientaciones. Cada cuenta cuenta con el **rol que tiene hoy**.
- **Visitantes**: son un grupo aparte. Como no se guardan sus consultas
  (RR_00_11), se cuentan sus filas de `tiempos_respuesta` resueltas o sin
  coincidencias: una ambigua y la especie que elige quedan como dos filas, así
  que cuenta cuando se resuelve. Hay datos desde la tabla 015.
- **Tipos de consulta**: la intención registrada (RR_33) de las consultas
  resueltas o sin coincidencias.
- **Tasa de éxito**: resueltas ÷ consultas contadas.
- Los días son en UTC, como el límite diario.
- **Al día (criterio 3)**: el panel vuelve a pedir las cifras cada 30 s
  (`hooks/useRecargaAutomatica.ts`) sin mostrar "Cargando…" ni cambiar el
  periodo, solo mientras se ve esa sección y la pestaña del navegador está
  visible; también con el botón "Actualizar".
- Las pruebas que pasan por la API dejan filas de visitante en
  `tiempos_respuesta` (RR_57), así que en la base local suben las cifras de
  "Visitante" después de correr pytest.

### Tiempo de respuesta (RR_57)

Cada `POST /consultas`, termine bien o con error, deja una fila en
`tiempos_respuesta` (015): cuánto tardó desde que llegó al backend hasta que la
respuesta quedó lista, cómo terminó (`resuelta`, `ambigua`, `tiempo_agotado`,
`error`…), el tipo de sesión y la especie. No se guarda el texto ni quién
consultó. Lo hace `services/tiempos.py`; si guardar falla, la consulta responde
igual.

- En el log: cada consulta queda con su duración, y las que pasan de
  `SEGUNDOS_RESPUESTA_LENTA` (30 por defecto, en el `.env`) como **WARNING**
  `RR_57: consulta lenta`. Cada llamada a CR-BioLM tiene además su propio
  tiempo, para ver qué parte tardó.
- En la API: `GET /admin/tiempos` (supermoderador) da el promedio, el p95, el
  máximo y cuántas fueron lentas en los últimos `dias` (7 por defecto), con las
  consultas más recientes; `solo_lentas=true` deja solo las lentas.

### Intención de cada consulta (RR_33)

La misma fila de `tiempos_respuesta` guarda la **intención** (tabla 017,
`dominio.IntencionConsulta`): el tipo de pregunta de RR_29 (`distribucion`,
`habitat`, `descripcion`, `general`) o el motivo de una orientación
(`saludo`, `ayuda`, `idioma`, `sin_sentido`, `fuera_de_tema`).

- Se fija antes de procesar, a partir del texto, así que queda también si la
  consulta se corta por tiempo o falla. Al terminar se precisa con lo que se
  respondió ("fuera de tema" solo se sabe después de buscar). De una consulta
  con `tipo_no_permitido` (RR_77) queda el tipo que se pidió.
- Cada fila tiene su `id` único y, si es de una cuenta, `consulta_id`. Del
  visitante no se guarda el texto.
- `GET /admin/tiempos` trae la `intencion` de cada registro y `por_intencion`:
  cuántas consultas hubo de cada una en el periodo. El log también la anota.

### Mapa y fuentes en las respuestas (RR_67, RR_68, RR_79, RR_80)

Si una respuesta incluye el mapa y las fuentes lo decide
`services/preferencias.py`, antes de guardar la consulta (así la conversación
reabierta muestra lo mismo que se respondió):

- **RR_80** — el supermoderador define el comportamiento por defecto en
  Administración → Respuestas (`configuracion_respuestas`, una sola fila).
  Aplica a todos los que no lo han cambiado: usuarios, visitantes y
  moderadores sin preferencia propia.
- **RR_67 y RR_68** — el moderador (y el supermoderador) cambia las suyas en
  Perfil → Preferencias. Se guardan en `usuarios.incluir_mapa` e
  `incluir_fuentes`; NULL = sigue la del sistema. Aplican desde la consulta
  siguiente.
- **RR_79** — como están en la cuenta, se conservan entre sesiones y cada
  moderador tiene las suyas.
- Sin mapa: `mapa = null` (el chat muestra solo el texto). Sin fuentes: sin la
  lista de fuentes, sin la procedencia (RR_45) y sin las citas 【…】 del texto.
  El pie "Fuentes: …" que CR-BioLM dibuja dentro del PNG del mapa no se puede
  quitar desde aquí.

### Leyenda del mapa (RR_48)

El PNG de CR-BioLM trae su leyenda, pero con el zoom del visor se agranda y se
corta. El frontend dibuja otra aparte (`config/leyendaMapa.ts`, con los mismos
colores que `habitat_map.py` de CR-BioLM): debajo del mapa se despliega y en el
visor queda fija encima del mapa. La **escala** está pendiente: hay que
acordarla con José (que CR-BioLM la dibuje o devuelva los km por píxel).

### Límite de consultas por rol (RR_62 a RR_66)

Cada rol tiene un límite (`roles.limite_consultas`) y un periodo
(`roles.periodo_consultas`: `dia`, `semana` o `mes`, `dominio.PeriodoConsultas`).
El visitante tiene `LIMITE_CONSULTAS_ANONIMO` por día. La lógica está en
`services/uso.py`.

- **RR_62 — restricción por rol**: antes de procesar una consulta se cuentan las
  resueltas del periodo; con el límite alcanzado se responde 429 sin llamar a
  CR-BioLM. Solo cobran las resueltas (orientación, ambiguas y sin coincidencias
  no).
- **RR_63 — el supermoderador define los límites**: pestaña "Roles y permisos"
  del panel (`components/admin/LimitesPorRol.tsx`), con `GET /admin/roles` y
  `PATCH /admin/roles/{rol}`. El límite debe ser un entero entre 1 y 100 000.
  No se acepta que el usuario estándar quede con tantas consultas como el
  moderador, ni con menos que un visitante (RR_62 criterio 3, RR_00_11); para
  comparar periodos distintos se llevan a consultas por día (el mes cuenta como
  30). El rechazo dice el mínimo o el máximo que sí se acepta con el periodo
  elegido ("Por semana, el mínimo es 36."), calculado con el
  `LIMITE_CONSULTAS_ANONIMO` del `.env`. Aplica a la siguiente consulta de cada cuenta y queda en la auditoría
  como `cambio_limite`, con quién lo hizo (trigger de la tabla 020).
- **RR_64 — restablecimiento periódico**: no hay contador que reiniciar; se
  cuentan las consultas resueltas desde el inicio del periodo actual. Los
  periodos empiezan a las **00:00 de Costa Rica** (la semana, el lunes; el mes,
  el día 1), no a la medianoche UTC. El contador del visitante también usa el
  día de Costa Rica.
- **RR_65 — aviso del límite**: el 429 dice el límite y cuándo se restablece
  ("Alcanzaste tu límite de 20 consultas por día. Se restablece el 20/10/2026 a
  las 00:00 (hora de Costa Rica)."). El chat lo avisa antes de enviar, con la
  misma fecha, y bloquea la caja de texto.
- **RR_66 — consultas restantes**: `GET /auth/sesion` trae
  `consultas_restantes`, `periodo_consultas` y `consultas_se_restablecen_en`; la
  barra lateral muestra "5/20 consultas hoy" (o "esta semana", "este mes") y se
  actualiza después de cada consulta resuelta.

---

## El catálogo de especies

Todo el sistema —servicios, routers, esquemas, frontend— depende solo de la
interfaz `FuenteCatalogo` (`Backend/app/services/catalogo.py`):

```python
buscar_especies(texto)                  -> list[EspecieCandidata]
obtener_especie(especie_id)             -> EspecieCandidata | None
construir_respuesta(especie_id, texto)  -> RespuestaConsulta | None
obtener_ficha(especie)                  -> FichaEspecie | None
obtener_mapa(especie_id)                -> bytes | None   (PNG)
```

`CATALOGO` en el `.env` elige la implementación:

- `demo` (por defecto): `CatalogoDemo`, datos de ejemplo en memoria (guaria
  morada, cedro amargo…). No necesita CR-BioLM; lo usan las pruebas.
- `crbiolm`: `CatalogoCRBioLM` (`services/catalogo_crbiolm.py`), datos reales
  por MCP. Necesita el servidor de CR-BioLM con las herramientas
  `get_occurrence_points` y `get_species_map_image`; `get_relevant_passage`
  (RR_44) es opcional: sin ella el texto sale de la ficha. Su `buscar_especies` es
  **provisional**: solo reconoce nombres científicos; la identificación de
  especies es del módulo de Jesús.

Los routers reciben el catálogo con `Depends(obtener_catalogo)`. En una prueba
se puede poner un catálogo falso con `app.dependency_overrides[obtener_catalogo]`.

**Mapas: todos vienen de CR-BioLM.** El backend no dibuja mapas propios. La
respuesta trae `mapa` (url, capas, puntos y advertencia) solo cuando CR-BioLM
genera uno con la herramienta `get_species_map_image` (fork de CR-BioLM); si no
lo genera, `mapa` es `null` y no se muestra ninguno. El PNG se pide aparte, con
sesión, a `GET /especies/{id}/mapa`. El catálogo de demostración no tiene mapas.

**Validación de los datos de CR-BioLM** (`services/validacion_datos.py`), antes
de armar la respuesta:

- **RR_60 — correspondencia exacta de especie**, en todas las fuentes. Una ficha
  del Manual cuyo nombre científico no es el pedido se descarta. GBIF y el mapa
  se piden con el nombre ya validado (CR-BioLM lo resuelve en GBIF exigiendo
  coincidencia exacta), y se descarta cada punto con coordenadas inválidas o
  fuera de Costa Rica.
- **RR_42 — consulta a GBIF**: CR-BioLM busca por el nombre científico (con
  coincidencia exacta en el catálogo de GBIF) y limpia las coordenadas. Pedirle
  solo registros de **presencia** (`occurrenceStatus=PRESENT`) es un cambio del
  lado de CR-BioLM, propuesto a José.
- **RR_43 — volumen mínimo**: con menos de `MINIMO_REGISTROS_MAPA` registros
  válidos (5 por defecto, el mismo mínimo con el que CR-BioLM dibuja los puntos)
  no se pide ni se muestra mapa; los registros sí se listan.
- **RR_58 — reintentos ante fallos de GBIF**: si `get_occurrence_points` falla,
  se reintenta hasta `GBIF_REINTENTOS` veces (2), esperando
  `GBIF_ESPERA_REINTENTO_SEGUNDOS` (2 s) entre intentos y sin pasarse del tiempo
  máximo de la consulta (RR_38). Si todos fallan, la respuesta sale con los datos
  del Manual, sin registros ni mapa.
- **RR_56 — actualización periódica de los datos de GBIF**: CR-BioLM guarda en
  disco los registros de GBIF de cada especie (`mpcr_rag/data/gbif_cache/`) y los
  vuelve a descargar cuando tienen más de `MPCR_GBIF_CACHE_MAX_DAYS` días (en el
  `.env` **de CR-BioLM**; ver "Levantar el servidor de CR-BioLM"). Los nuevos
  reemplazan a los anteriores solo si la descarga salió bien; si GBIF falla, se
  siguen usando los anteriores. `get_occurrence_points` dice cuándo los descargó
  (`updated_at`) y si son los anteriores porque no pudo actualizarlos (`stale`).
  La respuesta y la ficha traen esa fecha en `registros_actualizados_en`; el
  frontend la muestra junto a la cantidad de registros ("GBIF al 18/10/2026") y
  en "Origen de los datos". Con `stale`, la respuesta lo avisa. La descarga
  citable del paper de José (DOI 10.15468/dl.8yhee8) no cambia.

En los casos de RR_43, RR_56 y RR_58 la respuesta y la ficha traen el motivo en
`avisos`, que el frontend muestra (`components/Avisos.tsx`) y que también va en
el archivo descargado.

**Qué se pide según la pregunta** (`services/intencion.py`, provisional, por
palabras clave):

- **RR_41 — búsqueda geoespacial**: la consulta se clasifica por tipo
  (`TipoPregunta`): distribución ("¿dónde crece…?", altitud, provincia, mapa…),
  hábitat (RR_29, lista `HABITAT`), descripción ("¿cómo son las hojas…?",
  familia, usos) o general (solo el nombre). El tipo elige el texto (la
  morfología para descripción, el párrafo de distribución si no) y el campo
  `geoespacial` (false solo para descripción). Los registros de GBIF y el mapa
  se piden **siempre** que existan, porque RR_52, RR_46 y RR_59 piden mostrar
  la distribución y la cantidad de registros cuando hay datos.
- **RR_29 — clasificación del tipo de consulta**: hábitat = "hábitat",
  "ambiente", "bosque", "páramo", "epífita"… (lista `HABITAT`) más los tipos de
  bosque del vocabulario de CR-BioLM (`get_vocabulary`, el mismo que carga
  RR_39), sin los ambiguos ("roble", "seco", "húmedo"). Lo geográfico gana
  ("¿en qué provincia…?"), pero "crece" o "se encuentra" junto a una palabra de
  hábitat es hábitat ("¿en qué bosque crece…?"). Qué fuente da el texto según el
  tipo, si no lo redactó el LLM (RR_49) ni hay fragmento (RR_44):

  | Tipo | Texto |
  |---|---|
  | distribución, general | párrafo de distribución del Manual |
  | hábitat | campos de la ficha: forma de crecimiento, tipo de bosque, vertiente y elevación (`services/habitat.py`); sin esos datos, el párrafo de distribución |
  | descripción | morfología |

  La respuesta trae el `tipo`, que se registra con RR_33.
- **RR_44 — búsqueda semántica sobre el Manual**: si la consulta pregunta algo
  concreto, el texto de la respuesta es el fragmento del Manual de **esa**
  especie que mejor lo responde, buscado por significado en los datos
  vectorizados de CR-BioLM (herramienta `get_relevant_passage`, L1, sin costo).
  Si la herramienta no está o no encuentra nada, se usa el texto de la ficha:
  la morfología para preguntas descriptivas y, si no, el párrafo de distribución.
- **RR_45 — combinación de fuentes**: la ficha estructurada, el fragmento
  vectorizado, GBIF y el mapa se combinan, ya validados como de la misma
  especie, en un contexto único (`services/contexto_especie.py`), del que salen
  la respuesta y la ficha. Cada una trae `procedencia`: de dónde sale cada dato
  (especie, texto, elevación, registros, mapa). El frontend lo muestra en
  "Origen de los datos" (`components/OrigenDeLosDatos.tsx`) y en la descarga.
  Son textos para el usuario (p. ej. "GBIF — registros de presencia en Costa
  Rica, actualizados el 18/10/2026", RR_56): las citas técnicas de CR-BioLM, con
  los filtros de GBIF o los archivos del mapa, no se muestran.
- **RR_49 — respuesta en lenguaje natural**: si la consulta trae una pregunta,
  el texto lo redacta el LLM de CR-BioLM (herramienta `answer_question`, L2), con
  las citas del Manual dentro (`【Especie (Tomo V, p.779)】`, que el frontend
  muestra como "(Tomo V, p.779)"). Solo se usa si respondió sobre **una**
  especie (modo `A`) y todas sus citas son de la especie identificada (RR_60).
  Si la herramienta falla (p. ej. sin llave de OpenRouter), tarda más de
  `SEGUNDOS_MAXIMOS_REDACCION_IA` o responde otra cosa, se usa el texto del
  Manual de RR_44, sin error para el usuario. También cuando OpenRouter falla y
  CR-BioLM devuelve el error como texto (`"(síntesis no disponible: …)"`,
  `SINTESIS_NO_DISPONIBLE` en `catalogo_crbiolm.py`). La ficha (RR_20) no usa
  el LLM.

---

## Conexión con CR-BioLM (MCP)

Por orden del cliente, el backend usa CR-BioLM a través de su servidor MCP
(`mpcr_rag/mcp/server.py` en el repo de CR-BioLM). La única pieza del backend
que habla con ese servidor es **`Backend/app/services/mcp_cliente.py`**:

```python
from app.services import mcp_cliente

sobre = mcp_cliente.llamar("get_species", name="Quercus costaricensis")
sobre.valor        # los datos (dict)
sobre.cita         # "Manual de Plantas de Costa Rica, Tomo V, p. 779"  (RR_50)
sobre.fuente       # "MPCR", "GBIF", "MPCR+GBIF"...                     (RR_51)
sobre.advertencia  # aviso que se muestra junto al dato, si no está vacío
sobre.es_suficiente  # False cuando no hay datos suficientes             (RR_53)
```

Si algo falla lanza una subclase de `mcp_cliente.ErrorMCP`
(`MCPNoDisponible`, `MCPTiempoAgotado`, `MCPErrorHerramienta`,
`MCPRespuestaInvalida`), para que el router muestre el error con opción de
reintentar (RR_05). Detalles en el docstring del módulo.

### Levantar el servidor de CR-BioLM en desarrollo

CR-BioLM corre **fuera de Docker**, en la máquina anfitriona, porque necesita
los datos que entregó el cliente y que no están en su repositorio: van
descomprimidos en la raíz del clon de CR-BioLM (`data_raw/` y
`mpcr_rag/data/`). Desde esa raíz:

```bash
python -c "from mpcr_rag.mcp.server import server; server.run(transport='streamable-http', host='0.0.0.0', port=8765)"
```

- `host='0.0.0.0'` es obligatorio: si escucha solo en 127.0.0.1, rechaza las
  peticiones que llegan desde el contenedor (HTTP 421). Si Windows pregunta por
  el firewall, permitir solo redes privadas.
- El backend lo encuentra en `MCP_URL` (por defecto
  `http://host.docker.internal:8765/mcp`). Para comprobarlo:
  http://localhost:8000/mcp-check
- **Llave del LLM (RR_49).** `answer_question` necesita una llave de OpenRouter
  en el `.env` **de CR-BioLM** (en la raíz de su clon, no en el de este
  proyecto). La cuenta y la llave son gratuitas si se usa un modelo `:free`:

  ```
  OPENROUTER_API_KEY=sk-or-v1-...
  MPCR_ENRICH_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
  ```

  Los modelos gratuitos cambian (en octubre de 2026
  `nvidia/nemotron-3-super-120b-a12b:free` dejó de existir y la respuesta
  mostraba `(síntesis no disponible: 'choices')`); la guía de hosting de
  CR-BioLM trae el comando para listar los disponibles. No hay que quitar la
  línea `MPCR_ENRICH_MODEL`: sin ella CR-BioLM usa `openai/gpt-4o-mini`, que es
  de pago. Si CR-BioLM no carga el `.env` solo,
  antes de arrancarlo: `set -a; source .env; set +a`.
- Sin esa llave, `answer_question` falla o responde `insufficient`; el backend
  usa entonces el texto del Manual (ver RR_49 arriba).
- **Actualización de los registros de GBIF (RR_56).** También en el `.env` de
  CR-BioLM. Con 0 (el valor por defecto de CR-BioLM) los registros guardados no
  vencen nunca:

  ```
  MPCR_GBIF_CACHE_MAX_DAYS=30
  ```

  CR-BioLM los vuelve a descargar cuando alguien consulta una especie con
  registros vencidos, y esa persona espera la descarga. Para que no pase, se
  pueden actualizar todos de antemano (p. ej. de noche, con cron o el
  Programador de tareas de Windows), desde la raíz de CR-BioLM:

  ```bash
  python -m mpcr_rag.scripts.refresh_gbif            # los que tienen más de MPCR_GBIF_CACHE_MAX_DAYS
  python -m mpcr_rag.scripts.refresh_gbif --status   # última actualización y los más viejos
  ```

  Sale con código 1 si alguna especie no se pudo actualizar (se quedan sus
  registros anteriores). Cada intento queda en `mpcr_rag/data/gbif_cache/_refresh_log.jsonl`.

### En el deploy

CR-BioLM será un contenedor más en la red de Docker, con los datos del cliente
montados como volumen (nunca dentro de la imagen ni del repositorio: pesan y
el texto del Manual tiene derechos de autor). `MCP_URL` pasa a ser algo como
`http://crbiolm:8765/mcp` y ese servicio no se publica hacia internet.

### Versión del SDK

`requirements.txt` fija `mcp==1.12.4`. La serie 2.x (la que usa CR-BioLM en su
servidor) exige `pydantic>=2.12` y otras versiones de FastAPI y Uvicorn. El
cliente 1.12.4 se entiende con el servidor 2.x (el protocolo se negocia al
conectar); se probó contra el servidor real de CR-BioLM.

---

## Pruebas

```bash
docker compose exec backend python -m pytest tests -q
```

Cubren el hash de contraseñas, la validación y sanitización de entradas, los
roles, la administración de usuarios (`test_admin.py`, RR_69 a RR_75), la
auditoría, el perfil, el historial por conversaciones y el adaptador
MCP (`test_mcp_cliente.py`, con un servidor MCP falso: no necesita CR-BioLM). Las de
auditoría y conversaciones usan la base de datos del contenedor y borran lo que
crean al terminar.

Las piezas comunes están en `tests/conftest.py` (fixtures: `visitante`,
`sesion` que se deshace, `catalogo`…) y `tests/apoyo.py` (`crear_usuario`,
`iniciar_sesion`, `CatalogoQueNoSeUsa`…). Dos fixtures se aplican solos a todas
las pruebas, para que no dependan de la configuración local: el catálogo de
demostración y `todos_los_tipos_permitidos` (RR_77). Una prueba que necesite
leer los permisos de la BD lleva `@pytest.mark.permisos_de_la_bd`.

---

## Calidad del código

| Qué revisa | Backend | Frontend |
|---|---|---|
| Estilo y errores probables | `ruff check .` | `npm run lint` (ESLint) |
| Formato | `ruff format .` | — |
| Tipos | `mypy` | `npm run typecheck` (TypeScript) |

La configuración está en `Backend/pyproject.toml` y `Frontend/eslint.config.js`.
Para revisar todo a mano (el backend con pre-commit, ver abajo; el frontend
dentro de su contenedor):

```bash
pre-commit run --all-files
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
```

**Antes de cada commit (pre-commit).** El archivo `.pre-commit-config.yaml`
ejecuta ruff y mypy sobre los archivos de Python que cambiaron, y además
impide subir archivos de más de 1 MB (datos del cliente) o llaves privadas.
Se activa una vez por clon, con Python instalado en la máquina:

```bash
pip install pre-commit
pre-commit install
```

**En GitHub (Actions).** `.github/workflows/ci.yml` corre en cada push y pull
request: ruff, mypy, migraciones y pytest contra un Postgres de prueba; ESLint
y el build del frontend; y que los tipos del frontend coincidan con la API.

**Tipos del frontend generados desde la API.** `Frontend/src/types/api.ts` no
se escribe a mano: sale del contrato OpenAPI que FastAPI genera a partir de los
esquemas de Pydantic. `src/types/index.ts` solo les pone nombres. Si se cambia
un esquema del backend, con el backend levantado:

```bash
docker compose exec frontend npm run tipos
```

y TypeScript marca cada pantalla que haya que ajustar. Si se olvida, el paso
"Tipos del frontend al día con la API" de GitHub Actions falla.

---

## Notas de seguridad
- Los contenedores corren sin root.
- Las credenciales van en `.env` (fuera de Git), nunca en el código.
- Las contraseñas de usuario se guardan con hash (bcrypt), nunca en texto plano.
- `bcrypt` está fijado en 4.0.1: `passlib` 1.7.4 lee `bcrypt.__about__`, que las
  versiones 4.1 y posteriores eliminaron. Sin ese pin el hash falla al arrancar.
- El login responde lo mismo ante un correo inexistente y ante una contraseña
  incorrecta, para no revelar qué correos están registrados.
- Tras `INTENTOS_LOGIN_MAXIMOS` contraseñas incorrectas seguidas (5 por defecto)
  la cuenta se bloquea `MINUTOS_BLOQUEO_LOGIN` minutos (15 por defecto) y el
  login responde **423** con la duración del bloqueo (RR_00_05). Mientras dure
  se rechaza incluso la contraseña correcta; un login correcto reinicia el contador.
- Las reglas de contraseña se validan en el servidor, no solo en el navegador.
- Verificación de correo (RR_00_07): al registrarse se envía un enlace que vence
  en 24 horas y sirve una sola vez; hasta usarlo, el login responde **403** y la
  persona puede seguir como visitante. En la tabla `tokens` se guarda solo el
  hash SHA-256 del token. El envío usa Gmail (SMTP) con las variables `SMTP_*`
  del `.env`; sin ellas, el enlace se escribe en `docker compose logs backend`.
- Recuperación de contraseña (RR_00_06): `/auth/recuperar` envía un enlace que
  vence en 30 minutos y sirve una sola vez, y responde lo mismo exista o no la
  cuenta. Al guardar la contraseña nueva se quita el bloqueo de RR_00_05 y el
  correo queda verificado. Los enlaces de verificación y de recuperación no son
  intercambiables, y entre dos envíos a la misma cuenta hay al menos 60 segundos.
