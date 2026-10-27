"""Fixtures compartidas.

Cada test corre dentro de una transacción que se revierte al terminar. Con
join_transaction_mode="create_savepoint", los commit() de services y crud
solo cierran un savepoint: nada queda guardado en la base de Docker.
"""
from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import engine, get_session
from app.core.security import create_access_token
from app.main import app
from app.models import Alumno, Carrera, Catedra, Docente, Materia, Usuario
from app.models.usuario import Rol
from app.services import ausencias


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
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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
