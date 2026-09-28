import os

# --- base de datos ----------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]

# --- firma de tokens --------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
ALGORITMO_JWT = "HS256"

# Duración de la sesión de un usuario registrado.
# La expiración por inactividad (RR_00_04) es de otro sprint; por ahora el token
# simplemente vence a las 8 horas.
MINUTOS_EXPIRACION_TOKEN = int(os.environ.get("MINUTOS_EXPIRACION_TOKEN", "480"))

# El visitante anónimo (RR_00_11) no tiene cuenta, así que su token dura más:
# es solo el identificador del navegador para poder contarle las consultas.
MINUTOS_EXPIRACION_TOKEN_ANONIMO = int(
    os.environ.get("MINUTOS_EXPIRACION_TOKEN_ANONIMO", str(60 * 24 * 30))
)

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
