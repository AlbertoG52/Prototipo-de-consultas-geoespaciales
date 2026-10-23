import os

# --- base de datos ----------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]

# --- firma de tokens --------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
ALGORITMO_JWT = "HS256"

# RR_00_04 — expiración de la sesión por inactividad.
#
# El token de un usuario registrado vence a los N minutos de emitido y el
# frontend lo renueva (POST /auth/renovar) mientras la persona tenga actividad.
# Si deja de usar la aplicación durante N minutos, el token vence en el servidor
# y tiene que volver a iniciar sesión.
#
# N es configurable en dos niveles:
#   - MINUTOS_INACTIVIDAD_SESION: valor por defecto del sistema (.env).
#   - usuarios.minutos_inactividad: lo que la persona elija en su perfil,
#     restringido a OPCIONES_INACTIVIDAD. 0 significa "Nunca".
MINUTOS_INACTIVIDAD_SESION = max(int(os.environ.get("MINUTOS_INACTIVIDAD_SESION", "30")), 1)

# Opciones que el perfil ofrece (minutos). Deben coincidir con las del frontend
# (ProfilePage.tsx).
OPCIONES_INACTIVIDAD = (30, 60, 360, 720, 1440, 10080, 0)

# Con "Nunca" el token igual necesita un vencimiento; se usa este, y se sigue
# renovando con la actividad.
MINUTOS_TOKEN_SIN_INACTIVIDAD = 60 * 24 * 30

# El visitante anónimo (RR_00_11) no tiene cuenta, así que su token dura más:
# es solo el identificador del navegador para poder contarle las consultas.
MINUTOS_EXPIRACION_TOKEN_ANONIMO = int(
    os.environ.get("MINUTOS_EXPIRACION_TOKEN_ANONIMO", str(60 * 24 * 30))
)

# RR_00_05 — bloqueo temporal por intentos fallidos de inicio de sesión.
# Tras INTENTOS_LOGIN_MAXIMOS contraseñas incorrectas seguidas, la cuenta queda
# bloqueada MINUTOS_BLOQUEO_LOGIN minutos. Ambos se configuran en el .env.
INTENTOS_LOGIN_MAXIMOS = max(int(os.environ.get("INTENTOS_LOGIN_MAXIMOS", "5")), 1)
MINUTOS_BLOQUEO_LOGIN = max(int(os.environ.get("MINUTOS_BLOQUEO_LOGIN", "15")), 1)

# --- correo (RR_00_07) ------------------------------------------------------
# Cuenta de Gmail que envía los correos, con una contraseña de aplicación.
# Los valores reales van solo en el .env. Si SMTP_USUARIO o SMTP_PASSWORD están
# vacíos no se envía nada: el contenido del correo (con su enlace) se escribe
# en el log del backend, para poder desarrollar sin credenciales.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USUARIO = os.environ.get("SMTP_USUARIO", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()

# Dirección del frontend; es la base de los enlaces que van en los correos.
URL_FRONTEND = os.environ.get("URL_FRONTEND", "http://localhost:5173").rstrip("/")

# RR_00_07 criterio 1 — vigencia del enlace de verificación de correo.
HORAS_TOKEN_VERIFICACION = 24

# RR_00_06 criterio 2 — vigencia del enlace de recuperación de contraseña.
# Es más corta: el enlace permite cambiar la contraseña de la cuenta.
MINUTOS_TOKEN_RECUPERACION = 30

# --- límites de consultas ---------------------------------------------------
# RR_00_11: el visitante sin cuenta dispone de menos consultas
# diarias que un usuario registrado. El límite del usuario registrado sale de
# la tabla 'roles' (columna limite_consultas).
LIMITE_CONSULTAS_ANONIMO = int(os.environ.get("LIMITE_CONSULTAS_ANONIMO", "5"))

# --- reglas de contraseña ---------------------------------------------------
# bcrypt tiene un límite real de 72 bytes. El proyecto puede permitir contraseñas
# largas, pero al hashear con bcrypt se deben truncar a 72 bytes antes del hash.
LONGITUD_MINIMA_PASSWORD = 8
LONGITUD_MAXIMA_PASSWORD = 255

# --- consultas --------------------------------------------------------------
# RR_34 — máximo de caracteres de una consulta. Una más larga se rechaza con
# un aviso (schemas/consulta.py) y el campo de texto del chat lo muestra con un
# contador (lo recibe en GET /auth/sesion).
LONGITUD_MAXIMA_CONSULTA = 500

# RR_38 — tiempo máximo de procesamiento de UNA consulta, en segundos, desde
# que llega al backend hasta que la respuesta está lista. Si se supera, la
# consulta se corta, no se descuenta del límite diario y el usuario ve un
# mensaje con la opción de reintentarla. Abarca todas las llamadas a CR-BioLM
# de esa consulta, así que debe ser mayor que MCP_TIMEOUT_SEGUNDOS (el máximo
# de una sola llamada). Se configura en el .env.
SEGUNDOS_MAXIMOS_CONSULTA = max(float(os.environ.get("SEGUNDOS_MAXIMOS_CONSULTA", "120")), 1.0)

# RR_23 — máximo de letras mal escritas (cambiadas, faltantes o sobrantes) en un
# nombre científico para corregirlo antes de buscar (services/correccion.py).
LETRAS_MAXIMAS_CORRECCION = 2

# RR_28 — máximo de especies que se ofrecen cuando la consulta nombra solo un
# género del Manual ("Quercus"): las primeras en orden alfabético.
GENERO_OPCIONES_MAXIMAS = 5

# --- CR-BioLM por MCP (services/mcp_cliente.py) -------------------------------
# Dirección del servidor MCP de CR-BioLM. En desarrollo corre en la máquina
# anfitriona, fuera de Docker, porque necesita los datos que entregó el cliente
# (catálogo, DEM, shapefiles); por eso se llega a él por host.docker.internal.
# En el deploy será el nombre del servicio en la red de Docker, p. ej.
# http://crbiolm:8765/mcp. Ver la sección "Conexión con CR-BioLM" del README.
MCP_URL = os.environ.get("MCP_URL", "http://host.docker.internal:8765/mcp").strip()

# Tiempo máximo de UNA llamada a una herramienta, en segundos. Debe cubrir el
# caso más lento: una respuesta del LLM (hasta ~40 s) más un mapa generado en
# el momento (~10-15 s). El tiempo máximo de la consulta completa es
# SEGUNDOS_MAXIMOS_CONSULTA (RR_38): una llamada nunca se extiende más allá de
# lo que le queda a la consulta.
MCP_TIMEOUT_SEGUNDOS = max(float(os.environ.get("MCP_TIMEOUT_SEGUNDOS", "90")), 1.0)

# Reintentos cuando NO se pudo conectar con el servidor. Una llamada que llegó
# al servidor nunca se reintenta (podría cobrar dos veces una consulta al LLM).
MCP_REINTENTOS_CONEXION = max(int(os.environ.get("MCP_REINTENTOS_CONEXION", "2")), 0)
MCP_ESPERA_REINTENTO_SEGUNDOS = max(
    float(os.environ.get("MCP_ESPERA_REINTENTO_SEGUNDOS", "1")), 0.0
)

# RR_49 — tiempo máximo para que el LLM de CR-BioLM (answer_question) redacte la
# respuesta. Si se pasa, la respuesta sale con el texto del Manual en lugar de
# cortar la consulta. Los modelos gratuitos de OpenRouter pueden ser lentos.
SEGUNDOS_MAXIMOS_REDACCION_IA = max(
    float(os.environ.get("SEGUNDOS_MAXIMOS_REDACCION_IA", "45")), 1.0
)

# --- registros de GBIF (services/catalogo_crbiolm.py) --------------------------
# RR_43 — mínimo de registros de presencia válidos (ya filtrados por RR_60) para
# generar el mapa de una especie. Con menos, la respuesta sale sin mapa y con un
# aviso al usuario. 5 coincide con el mínimo con el que CR-BioLM dibuja los
# puntos de GBIF en sus mapas (render_species_map).
MINIMO_REGISTROS_MAPA = max(int(os.environ.get("MINIMO_REGISTROS_MAPA", "5")), 1)

# RR_58 — reintentos cuando CR-BioLM no logra consultar GBIF (la herramienta
# get_occurrence_points falla). Es seguro repetirla: es L1, no usa el LLM.
# Entre intentos se espera GBIF_ESPERA_REINTENTO_SEGUNDOS, salvo que a la
# consulta ya no le alcance el tiempo (RR_38). Si todos fallan, la respuesta
# sale con los datos del Manual, sin registros ni mapa, y avisa al usuario.
GBIF_REINTENTOS = max(int(os.environ.get("GBIF_REINTENTOS", "2")), 0)
GBIF_ESPERA_REINTENTO_SEGUNDOS = max(
    float(os.environ.get("GBIF_ESPERA_REINTENTO_SEGUNDOS", "2")), 0.0
)

# RR_57 — a partir de cuántos segundos una consulta se considera lenta. Las
# lentas se marcan en el log (WARNING) y en GET /admin/tiempos.
SEGUNDOS_RESPUESTA_LENTA = max(float(os.environ.get("SEGUNDOS_RESPUESTA_LENTA", "30")), 0.1)

# --- administración (services/admin.py) -----------------------------------------
# RR_76 — si el supermoderador ve el TEXTO de las consultas en el historial de
# uso de cada usuario. Con "false" sigue viendo cuántas hizo, cuándo, con qué
# resultado y de qué especie, pero no lo que escribió. Se configura en el .env.
_VALORES_SI = ("1", "true", "si", "sí")
ADMIN_VE_TEXTO_CONSULTAS = (
    os.environ.get("ADMIN_VE_TEXTO_CONSULTAS", "true").strip().lower() in _VALORES_SI
)

# Qué catálogo de especies usa el backend (services/catalogo.py):
#   demo     datos de ejemplo en memoria; no necesita CR-BioLM. Lo usan las pruebas.
#   crbiolm  datos reales del servidor MCP de CR-BioLM (MCP_URL).
CATALOGO = os.environ.get("CATALOGO", "demo").strip().lower()
if CATALOGO not in ("demo", "crbiolm"):
    raise ValueError(f"CATALOGO debe ser 'demo' o 'crbiolm', no {CATALOGO!r}")

# --- CORS -------------------------------------------------------------------
ORIGENES_PERMITIDOS = [
    o.strip()
    for o in os.environ.get(
        "ORIGENES_PERMITIDOS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
