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
LONGITUD_MAXIMA_CONSULTA = 500

# --- CORS -------------------------------------------------------------------
ORIGENES_PERMITIDOS = [
    o.strip()
    for o in os.environ.get(
        "ORIGENES_PERMITIDOS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
