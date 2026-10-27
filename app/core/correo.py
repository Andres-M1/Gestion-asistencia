"""Envío de correos con smtplib (HU-06).

Una sola conexión y un mensaje por destinatario (nunca todos en "Para").
Si falla un destinatario se registra en el log y se sigue con el resto.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def configurado() -> bool:
    return bool(settings.SMTP_HOST and (settings.SMTP_FROM or settings.SMTP_USER))


def enviar(destinatarios: list[str], asunto: str, texto: str) -> None:
    if not destinatarios:
        return
    if not configurado():
        logger.warning("SMTP no configurado (faltan SMTP_HOST o SMTP_USER/SMTP_FROM): no se envían %d correos",
                       len(destinatarios))
        return

    remitente = settings.SMTP_FROM or settings.SMTP_USER
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
            for destinatario in destinatarios:
                mensaje = EmailMessage()
                mensaje["From"] = remitente
                mensaje["To"] = destinatario
                mensaje["Subject"] = asunto
                mensaje.set_content(texto)
                try:
                    smtp.send_message(mensaje)
                except Exception:
                    logger.exception("No se pudo enviar el correo a %s", destinatario)
    except Exception:
        logger.exception("No se pudo usar el servidor SMTP %s:%s", settings.SMTP_HOST, settings.SMTP_PORT)
