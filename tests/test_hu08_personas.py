"""HU-08: el admin da de alta y edita docentes y alumnos (usuario + perfil).

DNIs de este archivo: 8100000x (no chocan con conftest ni con los datos de prueba).
"""
import pytest
from sqlmodel import select

from app.core.security import verify_password
from app.models import Alumno, Docente, Usuario
from app.models.usuario import Rol
from tests.conftest import auth

DOCENTES = "/api/v1/docentes/"
ALUMNOS = "/api/v1/alumnos/"


def nuevo(dni="81000001", email=None, **extra) -> dict:
    return {"dni": dni, "password": "clave-segura", "nombre": "Ana", "apellido": "Martínez",
            "email": email or f"persona.{dni}@gestion-test.com.ar", **extra}


def usuario_por_dni(session, dni) -> Usuario | None:
    return session.exec(select(Usuario).where(Usuario.dni == dni)).first()


@pytest.fixture
def admin(datos):
    return auth(datos["u_admin"])


@pytest.fixture
def carrera_id(datos):
    return datos["martes_a"].materia.carrera_id


# --- Alta -----------------------------------------------------------------------------

def test_alta_de_docente_crea_usuario_y_perfil(client, session, admin):
    r = client.post(DOCENTES, headers=admin, json=nuevo())
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo == {"id": cuerpo["id"], "dni": "81000001", "nombre": "Ana", "apellido": "Martínez",
                      "email": "persona.81000001@gestion-test.com.ar", "activo": True}

    usuario = usuario_por_dni(session, "81000001")
    assert usuario.rol == Rol.docente
    assert usuario.password_hash != "clave-segura"
    assert verify_password("clave-segura", usuario.password_hash)
    assert usuario.docente.id == cuerpo["id"]


def test_alta_de_alumno_crea_usuario_y_perfil_con_carrera(client, session, admin, carrera_id):
    r = client.post(ALUMNOS, headers=admin, json=nuevo(carrera_id=carrera_id))
    assert r.status_code == 201, r.text
    assert r.json()["carrera_id"] == carrera_id
    usuario = usuario_por_dni(session, "81000001")
    assert usuario.rol == Rol.estudiante
    assert usuario.alumno.id == r.json()["id"]


def test_si_falla_el_perfil_no_queda_el_usuario(client, session, admin, datos):
    """Usuario y perfil van en una sola transacción: con el email repetido no se crea ninguno."""
    r = client.post(DOCENTES, headers=admin, json=nuevo(email="doc.a@gestion-test.com.ar"))
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe un docente con ese email"}
    assert usuario_por_dni(session, "81000001") is None


@pytest.mark.parametrize("campo, valor", [
    ("dni", "12.345.678"), ("dni", "12345"), ("dni", "12345678901"), ("dni", "abcdefgh"),
    ("password", "corta"), ("email", "no-es-un-email"), ("nombre", ""), ("apellido", ""),
])
def test_validaciones_del_alta_dan_422(client, session, admin, campo, valor):
    r = client.post(DOCENTES, headers=admin, json={**nuevo(), campo: valor})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", campo]
    assert usuario_por_dni(session, "81000001") is None


def test_alumno_con_carrera_inexistente_da_422(client, session, admin):
    r = client.post(ALUMNOS, headers=admin, json=nuevo(carrera_id=999999999))
    assert r.status_code == 422
    assert r.json() == {"detail": "La carrera indicada no existe"}
    assert usuario_por_dni(session, "81000001") is None


@pytest.mark.parametrize("ruta", [DOCENTES, ALUMNOS])
def test_dni_duplicado_da_409(client, admin, carrera_id, ruta):
    extra = {"carrera_id": carrera_id} if ruta == ALUMNOS else {}
    r = client.post(ruta, headers=admin, json=nuevo(dni="80000001", **extra))  # DNI del docente A
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe un usuario con ese DNI"}


def test_email_de_alumno_duplicado_da_409(client, admin, carrera_id):
    r = client.post(ALUMNOS, headers=admin, json=nuevo(email="alu@gestion-test.com.ar", carrera_id=carrera_id))
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe un alumno con ese email"}


# --- Consulta ----------------------------------------------------------------------------

def test_obtener_y_listar(client, admin, datos):
    r = client.get(f"{DOCENTES}{datos['doc_a'].id}", headers=admin)
    assert r.status_code == 200
    assert r.json()["dni"] == "80000001"

    alumno = datos["u_alumno"].alumno
    r = client.get(ALUMNOS, headers=admin, params={"carrera_id": alumno.carrera_id})
    assert r.status_code == 200
    assert [a["dni"] for a in r.json()] == ["80000003"]


@pytest.mark.parametrize("ruta, mensaje", [(DOCENTES, "Docente no encontrado"), (ALUMNOS, "Alumno no encontrado")])
def test_id_inexistente_da_404(client, admin, ruta, mensaje):
    for metodo, cuerpo in (("GET", None), ("PATCH", {"nombre": "X"})):
        r = client.request(metodo, f"{ruta}999999999", headers=admin, json=cuerpo)
        assert r.status_code == 404
        assert r.json() == {"detail": mensaje}


# --- Edición -----------------------------------------------------------------------------

def test_patch_cambia_datos_y_contrasena(client, session, admin, datos):
    r = client.patch(f"{DOCENTES}{datos['doc_a'].id}", headers=admin,
                     json={"nombre": "Docente", "password": "clave-nueva-123"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Docente"
    assert r.json()["dni"] == "80000001"

    session.refresh(datos["u_doc_a"])
    assert verify_password("clave-nueva-123", datos["u_doc_a"].password_hash)
    login = client.post("/api/v1/auth/login", json={"dni": "80000001", "password": "clave-nueva-123"})
    assert login.status_code == 200


def test_patch_desactiva_al_alumno(client, session, admin, datos):
    alumno = datos["u_alumno"].alumno
    r = client.patch(f"{ALUMNOS}{alumno.id}", headers=admin, json={"activo": False})
    assert r.status_code == 200
    assert r.json()["activo"] is False
    session.refresh(datos["u_alumno"])
    assert datos["u_alumno"].activo is False


def test_patch_valida_contrasena_y_email(client, admin, datos):
    url = f"{DOCENTES}{datos['doc_a'].id}"
    assert client.patch(url, headers=admin, json={"password": "corta"}).status_code == 422
    r = client.patch(url, headers=admin, json={"email": "doc.b@gestion-test.com.ar"})
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe un docente con ese email"}


def test_patch_de_alumno_con_carrera_inexistente_da_422(client, admin, datos):
    r = client.patch(f"{ALUMNOS}{datos['u_alumno'].alumno.id}", headers=admin, json={"carrera_id": 999999999})
    assert r.status_code == 422
    assert r.json() == {"detail": "La carrera indicada no existe"}


def test_no_hay_delete_de_personas(client, admin, datos):
    assert client.delete(f"{DOCENTES}{datos['doc_a'].id}", headers=admin).status_code == 405
    assert client.delete(f"{ALUMNOS}{datos['u_alumno'].alumno.id}", headers=admin).status_code == 405


# --- Permisos -----------------------------------------------------------------------------

@pytest.mark.parametrize("quien", ["u_doc_a", "u_alumno"])
@pytest.mark.parametrize("ruta", [DOCENTES, ALUMNOS])
def test_solo_el_admin(client, datos, quien, ruta):
    assert client.get(ruta, headers=auth(datos[quien])).status_code == 403
    assert client.post(ruta, headers=auth(datos[quien]), json=nuevo()).status_code == 403


def test_sin_token_da_401(client):
    assert client.get(DOCENTES).status_code == 401


def test_modelos_sin_cambios_por_un_403(session, client, datos):
    client.post(DOCENTES, headers=auth(datos["u_doc_a"]), json=nuevo())
    assert usuario_por_dni(session, "81000001") is None
    assert session.exec(select(Docente).where(Docente.email == "persona.81000001@gestion-test.com.ar")).first() is None
    assert session.exec(select(Alumno).where(Alumno.email == "persona.81000001@gestion-test.com.ar")).first() is None
