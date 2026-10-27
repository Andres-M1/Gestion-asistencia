"""Notificaciones push con Firebase Cloud Messaging (HU-06).

Firebase se inicializa la primera vez que se usa, con el JSON del service
account indicado en FIREBASE_CREDENTIALS. Se envía multicast en tandas de
hasta TANDA tokens.
"""
import logging

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings

logger = logging.getLogger(__name__)

TANDA = 500  # máximo de tokens por mensaje multicast que acepta FCM

# Solo estos errores indican que el token ya no sirve. INVALID_ARGUMENT no se incluye:
# puede venir de un mensaje mal armado y borraría los tokens de todos.
TOKEN_INVALIDO = (messaging.UnregisteredError, messaging.SenderIdMismatchError)

_app = None


def configurado() -> bool:
    return bool(settings.FIREBASE_CREDENTIALS)


def _obtener_app():
    global _app
    if _app is None:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        _app = firebase_admin.initialize_app(cred, name="gestion-asist")
    return _app


def enviar(tokens: list[str], titulo: str, cuerpo: str) -> list[str]:
    """Envía el push a todos los tokens. Devuelve los que FCM rechazó por inválidos."""
    if not tokens:
        return []
    if not configurado():
        logger.warning("Firebase no configurado (falta FIREBASE_CREDENTIALS): no se envían %d push", len(tokens))
        return []
    try:
        app = _obtener_app()
    except Exception:
        logger.exception("No se pudo iniciar Firebase con %s", settings.FIREBASE_CREDENTIALS)
        return []

    invalidos = []
    for inicio in range(0, len(tokens), TANDA):
        tanda = tokens[inicio:inicio + TANDA]
        mensaje = messaging.MulticastMessage(
            tokens=tanda, notification=messaging.Notification(title=titulo, body=cuerpo)
        )
        try:
            respuesta = messaging.send_each_for_multicast(mensaje, app=app)
        except Exception:
            logger.exception("Falló el envío de una tanda de %d push", len(tanda))
            continue
        for token, resultado in zip(tanda, respuesta.responses):
            if resultado.success:
                continue
            if isinstance(resultado.exception, TOKEN_INVALIDO):
                invalidos.append(token)
            else:
                logger.warning("Push no enviado (%s): %s", type(resultado.exception).__name__, resultado.exception)
    return invalidos
