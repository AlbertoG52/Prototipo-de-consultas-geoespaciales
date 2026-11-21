import os

# --- base de datos ----------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]

# --- firma de tokens --------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
ALGORITMO_JWT = "HS256"

# Expiración de la sesión por inactividad.
#
# El token de una cuenta vence a los N minutos y el frontend lo renueva mientras haya
# actividad. N sale de usuarios.minutos_inactividad (elegido en el perfil, dentro de
# OPCIONES_INACTIVIDAD) o, si no hay, de MINUTOS_INACTIVIDAD_SESION. 0 significa "Nunca".
MINUTOS_INACTIVIDAD_SESION = max(int(os.environ.get("MINUTOS_INACTIVIDAD_SESION", "30")), 1)

# Opciones del perfil, en minutos. Deben coincidir con las de ProfilePage.tsx.
OPCIONES_INACTIVIDAD = (30, 60, 360, 720, 1440, 10080, 0)

# Con "Nunca" el token igual necesita un vencimiento; se usa este y se renueva con la
# actividad.
MINUTOS_TOKEN_SIN_INACTIVIDAD = 60 * 24 * 30

# El token del visitante solo identifica al navegador para contar sus consultas, por eso
# dura más.
MINUTOS_EXPIRACION_TOKEN_ANONIMO = int(
    os.environ.get("MINUTOS_EXPIRACION_TOKEN_ANONIMO", str(60 * 24 * 30))
)

# Bloqueo temporal tras INTENTOS_LOGIN_MAXIMOS contraseñas incorrectas seguidas, durante
# MINUTOS_BLOQUEO_LOGIN minutos.
INTENTOS_LOGIN_MAXIMOS = max(int(os.environ.get("INTENTOS_LOGIN_MAXIMOS", "5")), 1)
MINUTOS_BLOQUEO_LOGIN = max(int(os.environ.get("MINUTOS_BLOQUEO_LOGIN", "15")), 1)

# --- correo ------------------------------------------------------------------
# Cuenta de Gmail con contraseña de aplicación. Si SMTP_USUARIO o SMTP_PASSWORD están vacíos
# no se envía nada y el enlace se escribe en el log del backend.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USUARIO = os.environ.get("SMTP_USUARIO", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()

# Dirección del frontend; base de los enlaces de los correos.
URL_FRONTEND = os.environ.get("URL_FRONTEND", "http://localhost:5173").rstrip("/")

# Vigencia del enlace de verificación de correo.
HORAS_TOKEN_VERIFICACION = 24

# Vigencia del enlace de recuperación de contraseña.
MINUTOS_TOKEN_RECUPERACION = 30

# --- límites de consultas ---------------------------------------------------
# Límite diario del visitante sin cuenta. El de las cuentas sale de la tabla 'roles'.
LIMITE_CONSULTAS_ANONIMO = int(os.environ.get("LIMITE_CONSULTAS_ANONIMO", "5"))

# --- reglas de contraseña ---------------------------------------------------
# bcrypt solo usa los primeros 72 bytes; las contraseñas se truncan a ese largo antes del
# hash.
LONGITUD_MINIMA_PASSWORD = 8
LONGITUD_MAXIMA_PASSWORD = 255

# --- consultas --------------------------------------------------------------
# Máximo de caracteres de una consulta.
LONGITUD_MAXIMA_CONSULTA = 500

# Tiempo máximo de una consulta, en segundos, incluidas todas sus llamadas a CR-BioLM. Si se
# supera, la consulta se corta y no cuenta para el límite. Debe ser mayor que
# MCP_TIMEOUT_SEGUNDOS.
SEGUNDOS_MAXIMOS_CONSULTA = max(float(os.environ.get("SEGUNDOS_MAXIMOS_CONSULTA", "120")), 1.0)

# Máximo de letras mal escritas que se corrigen en un nombre científico
# (services/correccion.py).
LETRAS_MAXIMAS_CORRECCION = 2

# Máximo de frases de una consulta que se prueban como nombres comunes en CR-BioLM, de la
# más larga a la más corta (services/nombres_comunes.py).
NOMBRES_COMUNES_FRASES_MAXIMAS = 20

# Máximo de especies que se ofrecen cuando la consulta nombra solo un género ("Quercus").
GENERO_OPCIONES_MAXIMAS = 5

# --- CR-BioLM por MCP (services/mcp_cliente.py) -------------------------------
# Dirección del servidor MCP. En desarrollo corre en la máquina anfitriona, fuera de Docker,
# porque necesita los datos del cliente; en el deploy es el nombre del servicio, p. ej.
# http://crbiolm:8765/mcp.
MCP_URL = os.environ.get("MCP_URL", "http://host.docker.internal:8765/mcp").strip()

# Tiempo máximo de una llamada, en segundos: cubre una respuesta del LLM (~40 s) más un mapa
# (~15 s). Nunca excede lo que le queda a la consulta.
MCP_TIMEOUT_SEGUNDOS = max(float(os.environ.get("MCP_TIMEOUT_SEGUNDOS", "90")), 1.0)

# Reintentos solo cuando no se pudo conectar. Una llamada que llegó al servidor no se
# repite, para no pagar dos veces al LLM.
MCP_REINTENTOS_CONEXION = max(int(os.environ.get("MCP_REINTENTOS_CONEXION", "2")), 0)
MCP_ESPERA_REINTENTO_SEGUNDOS = max(
    float(os.environ.get("MCP_ESPERA_REINTENTO_SEGUNDOS", "1")), 0.0
)

# Llamadas pesadas (mapa, GBIF, LLM, búsqueda semántica) abiertas a la vez con CR-BioLM. Las
# demás esperan su turno dentro del tiempo de su consulta. 0 = sin límite.
MCP_LLAMADAS_SIMULTANEAS = max(int(os.environ.get("MCP_LLAMADAS_SIMULTANEAS", "3")), 0)

# Tiempo máximo para que el LLM de CR-BioLM redacte la respuesta. Si se pasa, se responde
# con el texto del Manual.
SEGUNDOS_MAXIMOS_REDACCION_IA = max(
    float(os.environ.get("SEGUNDOS_MAXIMOS_REDACCION_IA", "45")), 1.0
)

# --- registros de GBIF (services/catalogo_crbiolm.py) --------------------------
# Mínimo de registros válidos para generar el mapa; con menos, la respuesta sale sin mapa y
# con un aviso. Coincide con el mínimo que usa CR-BioLM para dibujar los puntos.
MINIMO_REGISTROS_MAPA = max(int(os.environ.get("MINIMO_REGISTROS_MAPA", "5")), 1)

# Reintentos cuando CR-BioLM no logra consultar GBIF, con una espera entre intentos si a la
# consulta le alcanza el tiempo. Si todos fallan, la respuesta sale con los datos del
# Manual, sin registros ni mapa.
GBIF_REINTENTOS = max(int(os.environ.get("GBIF_REINTENTOS", "2")), 0)
GBIF_ESPERA_REINTENTO_SEGUNDOS = max(
    float(os.environ.get("GBIF_ESPERA_REINTENTO_SEGUNDOS", "2")), 0.0
)

# Segundos a partir de los cuales una consulta se considera lenta (log y GET
# /admin/tiempos).
SEGUNDOS_RESPUESTA_LENTA = max(float(os.environ.get("SEGUNDOS_RESPUESTA_LENTA", "30")), 0.1)

# --- administración (services/admin.py) -----------------------------------------
# Si el supermoderador ve el texto de las consultas en el historial de uso de cada cuenta.
_VALORES_SI = ("1", "true", "si", "sí")
ADMIN_VE_TEXTO_CONSULTAS = (
    os.environ.get("ADMIN_VE_TEXTO_CONSULTAS", "true").strip().lower() in _VALORES_SI
)

# Catálogo de especies (services/catalogo.py):
#   demo     datos de ejemplo en memoria; lo usan las pruebas.
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
