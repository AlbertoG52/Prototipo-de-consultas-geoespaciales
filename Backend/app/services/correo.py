"""Envío de correos por SMTP — RR_00_07.

Usa smtplib de la biblioteca estándar, sin dependencias nuevas. La cuenta y su
contraseña de aplicación salen del .env (config.py).

Sin SMTP configurado no se envía nada: el correo se escribe en el log del
backend (docker compose logs backend), así se puede seguir el enlace mientras
se desarrolla.
"""

import logging
import smtplib
from email.message import EmailMessage

from ..config import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USUARIO

# El logger de uvicorn es el que ya aparece en los logs del contenedor.
logger = logging.getLogger("uvicorn.error")

NOMBRE_REMITENTE = "FloraBot CR"


def smtp_configurado() -> bool:
    return bool(SMTP_USUARIO and SMTP_PASSWORD)


def enviar_correo(destino: str, asunto: str, texto: str, html: str | None = None) -> None:
    """Envía un correo. Lanza la excepción de smtplib si el envío falla."""
    if not smtp_configurado():
        logger.warning(
            "SMTP sin configurar; el correo no se envió.\nPara: %s\nAsunto: %s\n\n%s",
            destino,
            asunto,
            texto,
        )
        return

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = f"{NOMBRE_REMITENTE} <{SMTP_USUARIO}>"
    mensaje["To"] = destino
    mensaje.set_content(texto)
    if html:
        mensaje.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as servidor:
        servidor.starttls()
        servidor.login(SMTP_USUARIO, SMTP_PASSWORD)
        servidor.send_message(mensaje)
