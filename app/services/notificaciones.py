"""Notificaciones de un aviso nuevo (HU-06) y token FCM de cada usuario.

Al registrarse un aviso:
  - correo a cada alumno con inscripción vigente en la cátedra y a todos los admins
    (preceptores) activos con email;
  - push a esos alumnos que tengan fcm_token.
Solo usuarios activos. Los destinatarios y el texto se arman durante el request
(FastAPI cierra la sesión de la base antes de correr los BackgroundTasks) y el
envío se hace en un único BackgroundTasks. Si algo falla se registra en el log:
el aviso ya quedó creado.
"""
import logging
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import BackgroundTasks
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select, update

from app.core import correo, push
from app.core.database import engine
from app.models.alumno import Alumno
from app.models.ausencia import Ausencia
from app.models.inscripcion import Inscripcion
from app.models.usuario import Rol, Usuario
from app.schemas.ausencia import AvisoDetalle

logger = logging.getLogger(__name__)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class Notificacion:
    emails: list[str]
    tokens: list[str]
    asunto: str
    texto: str
    titulo_push: str
    cuerpo_push: str


@contextmanager
def abrir_sesion():
    """Sesión propia para el BackgroundTasks. Los tests la reemplazan por la sesión del test."""
    with Session(engine) as session:
        yield session


def _destinatarios(session: Session, catedra_id: int) -> tuple[list[str], list[str]]:
    alumnos = session.exec(
        select(Alumno)
        .join(Inscripcion)
        .join(Usuario, Alumno.usuario_id == Usuario.id)
        .where(Inscripcion.catedra_id == catedra_id, Inscripcion.vigente == True, Usuario.activo == True)  # noqa: E712
        .options(selectinload(Alumno.usuario))
    ).all()
    admins = session.exec(
        select(Usuario).where(Usuario.rol == Rol.admin, Usuario.activo == True, Usuario.email.is_not(None))  # noqa: E712
    ).all()

    emails = [a.email for a in alumnos] + [u.email for u in admins]
    tokens = [a.usuario.fcm_token for a in alumnos if a.usuario.fcm_token]
    return list(dict.fromkeys(emails)), list(dict.fromkeys(tokens))  # sin repetidos, en orden


def _fecha(detalle: AvisoDetalle) -> str:
    return f"{DIAS[detalle.fecha.isoweekday() - 1]} {detalle.fecha:%d/%m/%Y}"


def _armar(detalle: AvisoDetalle, emails: list[str], tokens: list[str]) -> Notificacion:
    clase = f"{detalle.materia} {detalle.comision}"
    horario = f"{detalle.hora_inicio:%H:%M} a {detalle.hora_fin:%H:%M}"
    docente = f"{detalle.docente.nombre} {detalle.docente.apellido}"
    texto = (
        f"El docente {docente} no dará la clase de:\n\n"
        f"Materia:  {detalle.materia}\n"
        f"Comisión: {detalle.comision}\n"
        f"Fecha:    {_fecha(detalle)}\n"
        f"Horario:  {horario}\n"
    )
    return Notificacion(
        emails=emails,
        tokens=tokens,
        asunto=f"Aviso de ausencia: {clase} - {_fecha(detalle)}",
        texto=texto,
        titulo_push=f"Clase suspendida: {clase}",
        cuerpo_push=f"{_fecha(detalle)}, {horario}. Docente: {docente}",
    )


def programar(session: Session, aviso: Ausencia, detalle: AvisoDetalle, background_tasks: BackgroundTasks) -> None:
    """Arma los destinatarios y lanza el envío en segundo plano. Nunca lanza excepciones."""
    try:
        emails, tokens = _destinatarios(session, aviso.catedra_id)
        background_tasks.add_task(enviar, _armar(detalle, emails, tokens))
    except Exception:
        logger.exception("No se pudieron preparar las notificaciones del aviso %s", aviso.id)


def enviar(notificacion: Notificacion) -> None:
    """Tarea en segundo plano: correos, push y limpieza de tokens inválidos."""
    try:
        correo.enviar(notificacion.emails, notificacion.asunto, notificacion.texto)
        invalidos = push.enviar(notificacion.tokens, notificacion.titulo_push, notificacion.cuerpo_push)
        if invalidos:
            with abrir_sesion() as session:
                session.exec(update(Usuario).where(Usuario.fcm_token.in_(invalidos)).values(fcm_token=None))
                session.commit()
            logger.info("Se borraron %d tokens FCM inválidos", len(invalidos))
    except Exception:
        logger.exception("Falló el envío de notificaciones")


def asignar_token(session: Session, usuario: Usuario, token: str | None) -> None:
    """Guarda (o borra, con None) el token FCM del usuario.

    Un token identifica un celular: si otro usuario lo tenía (cerró sesión y entró
    alguien más en el mismo teléfono), se le quita para que no reciba push ajenos.
    """
    if token is not None:
        session.exec(
            update(Usuario).where(Usuario.fcm_token == token, Usuario.id != usuario.id).values(fcm_token=None)
        )
    usuario.fcm_token = token
    session.add(usuario)
    session.commit()


def advertir_si_falta_configuracion() -> None:
    """Se llama al arrancar la app: la app funciona igual, pero sin ese tipo de envío."""
    if not correo.configurado():
        logger.warning("SMTP no configurado: los avisos no enviarán correos (ver README, HU-06)")
    if not push.configurado():
        logger.warning("FIREBASE_CREDENTIALS no configurado: los avisos no enviarán push (ver README, HU-06)")
