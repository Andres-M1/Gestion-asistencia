"""Fixtures compartidas.

Cada test corre dentro de una transacción que se revierte al terminar. Con
join_transaction_mode="create_savepoint", los commit() de services y crud
solo cierran un savepoint: nada queda guardado en la base de Docker.

Ningún test envía correos ni push reales: la fixture autouse `envios`
reemplaza smtplib.SMTP y el envío de FCM por versiones falsas que registran
lo que se habría enviado.
"""
from contextlib import contextmanager
from datetime import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core import correo, push
from app.core.config import settings
from app.core.database import engine, get_session
from app.core.security import create_access_token
from app.main import app
from app.models import Alumno, Carrera, Catedra, Docente, Materia, Usuario
from app.models.usuario import Rol
from app.services import ausencias, notificaciones


@pytest.fixture
def session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(session, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session

    # El BackgroundTasks abre su propia sesión: en los tests, que use la del test
    @contextmanager
    def sesion_del_test():
        yield session

    monkeypatch.setattr(notificaciones, "abrir_sesion", sesion_del_test)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def envios(monkeypatch):
    """SMTP y FCM falsos para todos los tests. Por defecto, con configuración presente.

    - envios.correos: mensajes "enviados" (EmailMessage).
    - envios.tandas_push: lista de tandas de tokens enviadas a FCM.
    - envios.fallar_correo_a: emails cuyo envío falla.
    - envios.error_conexion_smtp / envios.error_fcm: excepción a lanzar (o None).
    - envios.error_por_token: {token: excepción} que FCM devuelve para ese token.
    """
    registro = SimpleNamespace(correos=[], tandas_push=[], fallar_correo_a=set(),
                               error_conexion_smtp=None, error_fcm=None, error_por_token={})

    class SMTPFalso:
        def __init__(self, host, port, timeout=None):
            if registro.error_conexion_smtp:
                raise registro.error_conexion_smtp

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, usuario, password):
            pass

        def send_message(self, mensaje):
            if mensaje["To"] in registro.fallar_correo_a:
                raise OSError(f"fallo simulado enviando a {mensaje['To']}")
            registro.correos.append(mensaje)

    def fcm_falso(mensaje, app=None):
        if registro.error_fcm:
            raise registro.error_fcm
        registro.tandas_push.append(list(mensaje.tokens))
        respuestas = []
        for token in mensaje.tokens:
            error = registro.error_por_token.get(token)
            respuestas.append(SimpleNamespace(success=error is None, exception=error))
        return SimpleNamespace(responses=respuestas)

    monkeypatch.setattr(correo.smtplib, "SMTP", SMTPFalso)
    monkeypatch.setattr(push.messaging, "send_each_for_multicast", fcm_falso)
    monkeypatch.setattr(push, "_obtener_app", lambda: object())
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.falso.test")
    monkeypatch.setattr(settings, "SMTP_USER", "avisos@gestion-test.com.ar")
    monkeypatch.setattr(settings, "SMTP_FROM", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS", "secrets/falso.json")
    return registro


@pytest.fixture
def fijar_ahora(monkeypatch):
    """Devuelve una función para fijar la hora "actual" que usan las reglas de avisos."""
    def fijar(momento):
        monkeypatch.setattr(ausencias, "ahora", lambda: momento)
    return fijar


def auth(usuario: Usuario) -> dict:
    """Encabezado Authorization para un usuario (sin pasar por el login)."""
    return {"Authorization": f"Bearer {create_access_token(usuario.id, usuario.rol.value)}"}


def _usuario(session: Session, dni: str, rol: Rol) -> Usuario:
    # password_hash ficticio: estos tests no usan el login, y así evitan el costo de Argon2
    usuario = Usuario(dni=dni, password_hash="x", rol=rol)
    session.add(usuario)
    session.commit()
    return usuario


@pytest.fixture
def datos(session):
    """Carrera, materias, dos docentes con sus cátedras, un alumno y un admin.

    Docente A: "Programación II" 1K1 martes 18-20 y "Programación II" 1K2 lunes 18-20.
    Docente B: "Base de Datos" 1K3 martes 18-20.
    """
    carrera = Carrera(nombre="TEST Sistemas")
    session.add(carrera)
    session.commit()
    prog = Materia(carrera_id=carrera.id, nombre="Programación II")
    bd = Materia(carrera_id=carrera.id, nombre="Base de Datos")
    session.add_all([prog, bd])
    session.commit()

    def docente(dni: str, email: str) -> Docente:
        d = Docente(usuario_id=_usuario(session, dni, Rol.docente).id, nombre="Doc", apellido=dni, email=email)
        session.add(d)
        session.commit()
        return d

    doc_a = docente("80000001", "doc.a@gestion-test.com.ar")
    doc_b = docente("80000002", "doc.b@gestion-test.com.ar")

    def catedra(materia, doc, comision, dia) -> Catedra:
        c = Catedra(materia_id=materia.id, docente_id=doc.id, comision=comision, dia_semana=dia,
                    hora_inicio=time(18, 0), hora_fin=time(20, 0))
        session.add(c)
        session.commit()
        return c

    martes_a = catedra(prog, doc_a, "1K1", 2)
    lunes_a = catedra(prog, doc_a, "1K2", 1)
    martes_b = catedra(bd, doc_b, "1K3", 2)

    u_alumno = _usuario(session, "80000003", Rol.estudiante)
    session.add(Alumno(usuario_id=u_alumno.id, carrera_id=carrera.id, nombre="Alu", apellido="Test",
                       email="alu@gestion-test.com.ar"))
    session.commit()

    return {
        "doc_a": doc_a, "doc_b": doc_b,
        "martes_a": martes_a, "lunes_a": lunes_a, "martes_b": martes_b,
        "u_doc_a": doc_a.usuario, "u_doc_b": doc_b.usuario,
        "u_alumno": u_alumno,
        "u_admin": _usuario(session, "80000004", Rol.admin),
        "u_docente_sin_perfil": _usuario(session, "80000005", Rol.docente),
    }
