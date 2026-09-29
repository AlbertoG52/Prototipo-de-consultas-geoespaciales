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

## URLs
- Frontend: http://localhost:5173
- API:      http://localhost:8000/health  y  http://localhost:8000/db-check
- API docs: http://localhost:8000/docs
- Postgres: localhost:5432 (para inspeccionar con pgAdmin/DBeaver, opcional)

## Modo AWS (demos e integración)
Por defecto todo corre local. Para conectar el backend a la base de datos de AWS:
```bash
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```
Requiere el certificado en `certs/` y `DATABASE_URL_AWS` en el `.env`. Pasos completos en [`certs/README.md`](certs/README.md).

---

## Arquitectura

```
Backend/
  migrations/      esquema de la BD, un archivo por cambio
  app/
    config.py      variables de entorno y límites
    db.py          engine, sesión por petición
    security.py    hash de contraseñas, tokens, identidad de la petición
    main.py        montaje de la API
    models/        mapeo SQLAlchemy de las tablas que crean las migraciones
    schemas/       entrada y salida (Pydantic)
    routers/       endpoints HTTP
    services/      lógica que no es HTTP ni BD
  tests/           pruebas unitarias

Frontend/src/
  types/           tipos compartidos con la API
  services/api.ts  única puerta de salida hacia el backend
  context/         AuthContext (sesión) y ConsultasContext (conversación)
  pages/           vistas
  routes.tsx       enrutamiento
```

Dos reglas que conviene mantener:

1. **Ninguna vista llama a `fetch` directamente.** Todo pasa por `services/api.ts`,
   para que el manejo del token y de los errores viva en un solo lugar.
2. **Los modelos no crean tablas.** `db.py` no llama a `create_all()`. El esquema
   es de las migraciones; los modelos solo lo mapean.

### La sesión siempre existe

Root es la primera vista y no está protegida (RR_00_11). Si no hay token, el
frontend pide uno anónimo y la persona entra directo al agente. Iniciar sesión
es opcional y sirve para dos cosas: conservar el historial y tener más consultas
al día. Cerrar sesión no deja a nadie fuera, devuelve a la sesión anónima.

| | Visitante | Usuario registrado |
|---|---|---|
| Consultas diarias | 5 (`LIMITE_CONSULTAS_ANONIMO`) | 20 (`roles.limite_consultas`) |
| Historial | en memoria, se pierde al recargar | guardado en `consultas` |
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

Para agregar un cambio:
1. Se crea un archivo nuevo, p.ej. `011_....sql`.
2. Se guarda y se sube al repositorio de git.
3. Se ejecuta `git pull` y, al levantar Docker (o con `docker compose exec backend python migrate.py`),
   se realizan los cambios solo si aplica.

Regla: **ningún cambio a la BD se hace a mano; todo va en una migración versionada en Git.**

---

## Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| POST | `/auth/registro` | crear cuenta |
| POST | `/auth/login` | iniciar sesión |
| POST | `/auth/anonimo` | entrar sin cuenta |
| POST | `/auth/logout` | cerrar la sesión activa |
| GET | `/auth/sesion` | quién soy y cuántas consultas me quedan |
| POST | `/consultas` | enviar una consulta |
| GET | `/consultas/historial` | consultas de la sesión activa |

`POST /consultas` devuelve uno de tres estados:

- `resuelta` — trae `respuesta`; es la única que descuenta del límite diario.
- `ambigua` — trae `candidatos`. El frontend muestra las opciones y reenvía la
  misma consulta con `especie_id` (RR_17). Desambiguar no cuesta una consulta.
- `sin_coincidencias` — no se reconoció ninguna especie.

---

## El catálogo de especies es provisional

`Backend/app/services/catalogo.py` **no es la fuente de datos definitiva.** Los
módulos 2 y 3 no son de este sprint y el catálogo real vendrá de la API de
CR-BioLM, cuyo contrato todavía no está congelado.

RR_17 y RR_18 necesitan datos para que su lógica exista, así que ese archivo
tiene un catálogo de ejemplo. Todo lo demás —routers, esquemas, frontend,
pruebas— está escrito contra sus dos funciones públicas:

```python
buscar_especies(texto)              -> list[EspecieCandidata]
construir_respuesta(especie_id, t)  -> RespuestaConsulta
```

Cuando llegue la API real se reescribe **solo ese archivo**, respetando esas dos
firmas. Nada más del proyecto cambia. Las pruebas de `test_catalogo.py`
verifican comportamiento y no datos, así que siguen sirviendo después.

---

## Pruebas

```bash
docker compose exec backend python -m pytest tests -q
```

20 pruebas unitarias sobre el hash de contraseñas, la validación de entrada y la
lógica de coincidencias. No necesitan base de datos.

---

## Notas de seguridad
- Los contenedores corren sin root.
- Las credenciales van en `.env` (fuera de Git), nunca en el código.
- Las contraseñas de usuario se guardan con hash (bcrypt), nunca en texto plano.
- `bcrypt` está fijado en 4.0.1: `passlib` 1.7.4 lee `bcrypt.__about__`, que las
  versiones 4.1 y posteriores eliminaron. Sin ese pin el hash falla al arrancar.
- El login responde lo mismo ante un correo inexistente y ante una contraseña
  incorrecta, para no revelar qué correos están registrados.
- Las reglas de contraseña se validan en el servidor, no solo en el navegador.
