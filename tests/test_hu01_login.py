"""HU-01: login con DNI y contraseña, /auth/me y validación del token en cada request.

Los usuarios de este archivo tienen contraseña real (Argon2): el login la verifica.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.security import ALGORITHM, hash_password
from tests.conftest import auth

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
PASSWORD = "clave-de-prueba"
INCORRECTO = {"detail": "DNI o contraseña incorrectos"}


@pytest.fixture
def con_clave(session, datos):
    """El docente A, el alumno y el admin de conftest, con una contraseña real."""
    for clave in ("u_doc_a", "u_alumno", "u_admin"):
        datos[clave].password_hash = hash_password(PASSWORD)
        session.add(datos[clave])
    session.commit()
    return datos


def login(client, dni, password=PASSWORD):
    return client.post(LOGIN, json={"dni": dni, "password": password})


def token_con(payload: dict, clave: str = settings.SECRET_KEY) -> dict:
    return {"Authorization": f"Bearer {jwt.encode(payload, clave, algorithm=ALGORITHM)}"}


# --- Login --------------------------------------------------------------------------

def test_login_correcto_devuelve_un_token_bearer_con_id_y_rol(client, con_clave):
    usuario = con_clave["u_doc_a"]
    r = login(client, usuario.dni)
    assert r.status_code == 200, r.text
    assert r.json()["token_type"] == "bearer"
    payload = jwt.decode(r.json()["access_token"], settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == str(usuario.id)
    assert payload["rol"] == "docente"
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


def test_el_token_del_login_sirve_para_los_endpoints(client, con_clave):
    token = login(client, con_clave["u_doc_a"].dni).json()["access_token"]
    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["dni"] == con_clave["u_doc_a"].dni


def test_contrasena_incorrecta_da_401(client, con_clave):
    r = login(client, con_clave["u_doc_a"].dni, "otra-clave")
    assert r.status_code == 401
    assert r.json() == INCORRECTO
    assert r.headers["www-authenticate"] == "Bearer"


def test_dni_inexistente_da_401_con_el_mismo_mensaje(client, con_clave):
    r = login(client, "89999999")
    assert r.status_code == 401
    assert r.json() == INCORRECTO


def test_usuario_inactivo_da_401_con_el_mismo_mensaje(client, con_clave, session):
    usuario = con_clave["u_doc_a"]
    usuario.activo = False
    session.add(usuario)
    session.commit()
    r = login(client, usuario.dni)
    assert r.status_code == 401
    assert r.json() == INCORRECTO


def test_dni_inexistente_igual_verifica_una_contrasena(client, monkeypatch):
    """Se verifica contra un hash ficticio para que la demora no revele qué DNIs existen."""
    from app.services import auth as servicio
    verificados = []
    original = servicio.verify_password
    monkeypatch.setattr(servicio, "verify_password", lambda p, h: verificados.append(h) or original(p, h))
    login(client, "89999999")
    assert verificados == [servicio._HASH_FICTICIO]


def test_login_sin_password_da_422(client):
    r = client.post(LOGIN, json={"dni": "12345678"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "password"]


def test_login_oauth2_para_el_boton_authorize_de_docs(client, con_clave):
    r = client.post("/api/v1/auth/token", data={"username": con_clave["u_admin"].dni, "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["token_type"] == "bearer"


# --- /auth/me -----------------------------------------------------------------------

def test_me_de_docente_trae_su_perfil(client, datos):
    r = client.get(ME, headers=auth(datos["u_doc_a"]))
    assert r.status_code == 200
    assert r.json() == {
        "id": datos["u_doc_a"].id, "dni": "80000001", "rol": "docente",
        "perfil": {"id": datos["doc_a"].id, "nombre": "Doc", "apellido": "80000001",
                   "email": "doc.a@gestion-test.com.ar"},
    }


def test_me_de_alumno_trae_su_perfil(client, datos):
    r = client.get(ME, headers=auth(datos["u_alumno"]))
    assert r.status_code == 200
    assert r.json()["rol"] == "estudiante"
    assert r.json()["perfil"] == {"id": datos["u_alumno"].alumno.id, "nombre": "Alu", "apellido": "Test",
                                  "email": "alu@gestion-test.com.ar"}


def test_me_de_admin_no_tiene_perfil(client, datos):
    r = client.get(ME, headers=auth(datos["u_admin"]))
    assert r.status_code == 200
    assert r.json() == {"id": datos["u_admin"].id, "dni": "80000004", "rol": "admin", "perfil": None}


# --- Token inválido -------------------------------------------------------------------

def test_sin_token_da_401(client):
    r = client.get(ME)
    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


def _expira(minutos: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutos)


@pytest.mark.parametrize("caso", ["vencido", "otra_clave", "basura", "sin_sub", "sub_no_numerico", "usuario_inexistente"])
def test_token_invalido_da_401(client, datos, caso):
    sub = str(datos["u_doc_a"].id)
    encabezados = {
        "vencido": lambda: token_con({"sub": sub, "rol": "docente", "exp": _expira(-1)}),
        "otra_clave": lambda: token_con({"sub": sub, "rol": "docente", "exp": _expira(5)}, "otra-clave-de-firma-de-32-bytes!"),
        "basura": lambda: {"Authorization": "Bearer esto-no-es-un-jwt"},
        "sin_sub": lambda: token_con({"rol": "docente", "exp": _expira(5)}),
        "sub_no_numerico": lambda: token_con({"sub": "abc", "rol": "docente", "exp": _expira(5)}),
        "usuario_inexistente": lambda: token_con({"sub": "999999999", "rol": "docente", "exp": _expira(5)}),
    }[caso]()
    r = client.get(ME, headers=encabezados)
    assert r.status_code == 401
    assert r.json() == {"detail": "Token inválido o expirado"}


def test_usuario_desactivado_despues_de_loguearse_da_401(client, con_clave):
    """El token sigue sin vencer, pero el usuario ya no está activo: se corta al instante."""
    docente = con_clave["u_doc_a"]
    token = login(client, docente.dni).json()["access_token"]
    r = client.patch(f"/api/v1/docentes/{con_clave['doc_a'].id}", headers=auth(con_clave["u_admin"]),
                     json={"activo": False})
    assert r.status_code == 200, r.text

    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Token inválido o expirado"}
    assert login(client, docente.dni).json() == INCORRECTO

