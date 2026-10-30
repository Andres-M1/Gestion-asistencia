"""ABM del admin para cargar los datos: carreras, materias e inscripciones.

También cubre manejar_integridad (app/api/errores.py): unicidad -> 409, clave
foránea y CHECK -> 422, borrado con registros asociados -> 409.
Los nombres empiezan con "TEST" para no chocar con los datos de desarrollo.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.api.errores import manejar_integridad
from app.models import Inscripcion
from tests.conftest import auth

CARRERAS = "/api/v1/carreras/"
MATERIAS = "/api/v1/materias/"
INSCRIPCIONES = "/api/v1/inscripciones/"
SE_USA = {"detail": "No se puede borrar: tiene registros asociados"}


@pytest.fixture
def admin(datos):
    return auth(datos["u_admin"])


def crear(client, admin, ruta, cuerpo) -> dict:
    r = client.post(ruta, headers=admin, json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


# --- Carreras --------------------------------------------------------------------------

def test_carrera_alta_consulta_edicion_y_borrado(client, admin):
    carrera = crear(client, admin, CARRERAS, {"nombre": "TEST Química"})
    assert carrera == {"id": carrera["id"], "nombre": "TEST Química"}
    url = f"{CARRERAS}{carrera['id']}"

    assert client.get(url, headers=admin).json() == carrera
    assert client.patch(url, headers=admin, json={"nombre": "TEST Química Industrial"}).json()["nombre"] == \
        "TEST Química Industrial"
    assert client.delete(url, headers=admin).status_code == 204
    assert client.get(url, headers=admin).json() == {"detail": "Carrera no encontrada"}


def test_carrera_duplicada_da_409(client, admin):
    otra = crear(client, admin, CARRERAS, {"nombre": "TEST Química"})
    r = client.post(CARRERAS, headers=admin, json={"nombre": "TEST Sistemas"})  # la de conftest
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe una carrera con ese nombre"}
    r = client.patch(f"{CARRERAS}{otra['id']}", headers=admin, json={"nombre": "TEST Sistemas"})
    assert r.status_code == 409


def test_carrera_sin_nombre_da_422(client, admin):
    assert client.post(CARRERAS, headers=admin, json={"nombre": ""}).status_code == 422


def test_borrar_carrera_con_materias_y_alumnos_da_409(client, admin, datos):
    r = client.delete(f"{CARRERAS}{datos['martes_a'].materia.carrera_id}", headers=admin)
    assert r.status_code == 409
    assert r.json() == SE_USA


# --- Materias ----------------------------------------------------------------------------

def test_materia_alta_listado_por_carrera_y_borrado(client, admin):
    carrera = crear(client, admin, CARRERAS, {"nombre": "TEST Química"})
    materia = crear(client, admin, MATERIAS, {"carrera_id": carrera["id"], "nombre": "Química I"})
    assert materia == {"id": materia["id"], "carrera_id": carrera["id"], "nombre": "Química I"}

    r = client.get(MATERIAS, headers=admin, params={"carrera_id": carrera["id"]})
    assert r.json() == [materia]

    # Con una materia, la carrera ya no se puede borrar; sin ella, sí
    assert client.delete(f"{CARRERAS}{carrera['id']}", headers=admin).json() == SE_USA
    assert client.delete(f"{MATERIAS}{materia['id']}", headers=admin).status_code == 204
    assert client.delete(f"{CARRERAS}{carrera['id']}", headers=admin).status_code == 204


def test_materia_con_carrera_inexistente_da_422(client, admin):
    r = client.post(MATERIAS, headers=admin, json={"carrera_id": 999999999, "nombre": "Química I"})
    assert r.status_code == 422
    assert r.json() == {"detail": "La carrera indicada no existe"}


def test_borrar_materia_con_catedras_da_409(client, admin, datos):
    r = client.delete(f"{MATERIAS}{datos['martes_a'].materia_id}", headers=admin)
    assert r.status_code == 409
    assert r.json() == SE_USA


def test_materia_inexistente_da_404(client, admin):
    r = client.patch(f"{MATERIAS}999999999", headers=admin, json={"nombre": "X"})
    assert r.status_code == 404
    assert r.json() == {"detail": "Materia no encontrada"}


# --- Inscripciones ---------------------------------------------------------------------

@pytest.fixture
def inscripcion(client, admin, datos):
    return crear(client, admin, INSCRIPCIONES,
                 {"alumno_id": datos["u_alumno"].alumno.id, "catedra_id": datos["martes_a"].id})


def test_inscripcion_alta_queda_vigente(inscripcion, datos):
    assert inscripcion == {"id": inscripcion["id"], "alumno_id": datos["u_alumno"].alumno.id,
                           "catedra_id": datos["martes_a"].id, "vigente": True}


def test_inscripcion_duplicada_da_409(client, admin, datos, inscripcion):
    r = client.post(INSCRIPCIONES, headers=admin,
                    json={"alumno_id": inscripcion["alumno_id"], "catedra_id": inscripcion["catedra_id"]})
    assert r.status_code == 409
    assert r.json() == {"detail": "El alumno ya está inscripto en esa cátedra"}


@pytest.mark.parametrize("campo, mensaje", [
    ("alumno_id", "El alumno indicado no existe"),
    ("catedra_id", "La cátedra indicada no existe"),
])
def test_inscripcion_con_alumno_o_catedra_inexistente_da_422(client, admin, datos, campo, mensaje):
    cuerpo = {"alumno_id": datos["u_alumno"].alumno.id, "catedra_id": datos["martes_a"].id, campo: 999999999}
    r = client.post(INSCRIPCIONES, headers=admin, json=cuerpo)
    assert r.status_code == 422
    assert r.json() == {"detail": mensaje}


def test_baja_de_inscripcion_con_vigente_false(client, admin, datos, inscripcion):
    """La inscripción no se borra: el alumno deja de verla y queda el registro."""
    alumno = auth(datos["u_alumno"])
    assert [i["catedra_id"] for i in client.get("/api/v1/alumno/inscripciones", headers=alumno).json()] == \
        [datos["martes_a"].id]

    r = client.patch(f"{INSCRIPCIONES}{inscripcion['id']}", headers=admin, json={"vigente": False})
    assert r.status_code == 200
    assert r.json()["vigente"] is False

    assert client.get("/api/v1/alumno/inscripciones", headers=alumno).json() == []
    r = client.get(INSCRIPCIONES, headers=admin, params={"alumno_id": inscripcion["alumno_id"], "vigente": False})
    assert [i["id"] for i in r.json()] == [inscripcion["id"]]


def test_patch_de_inscripcion_requiere_vigente(client, admin, inscripcion):
    assert client.patch(f"{INSCRIPCIONES}{inscripcion['id']}", headers=admin, json={}).status_code == 422


def test_listar_inscripciones_por_catedra(client, admin, datos, inscripcion):
    r = client.get(INSCRIPCIONES, headers=admin, params={"catedra_id": datos["martes_a"].id})
    assert [i["id"] for i in r.json()] == [inscripcion["id"]]


def test_borrar_inscripcion(client, session, admin, inscripcion):
    assert client.delete(f"{INSCRIPCIONES}{inscripcion['id']}", headers=admin).status_code == 204
    assert session.get(Inscripcion, inscripcion["id"]) is None
    r = client.get(f"{INSCRIPCIONES}{inscripcion['id']}", headers=admin)
    assert r.json() == {"detail": "Inscripción no encontrada"}


# --- Permisos ----------------------------------------------------------------------------

@pytest.mark.parametrize("ruta", [CARRERAS, MATERIAS, INSCRIPCIONES])
@pytest.mark.parametrize("quien", ["u_doc_a", "u_alumno"])
def test_solo_el_admin(client, datos, ruta, quien):
    assert client.get(ruta, headers=auth(datos[quien])).status_code == 403


# --- manejar_integridad --------------------------------------------------------------------

def _violar(session, sql: str, **opciones):
    with pytest.raises(HTTPException) as error:
        with manejar_integridad(session, **opciones):
            session.execute(text(sql))
            session.commit()
    return error.value


def test_integridad_clave_foranea_da_422_con_su_mensaje(session):
    e = _violar(session, "INSERT INTO materia (carrera_id, nombre) VALUES (999999999, 'X')")
    assert (e.status_code, e.detail) == (422, "La carrera indicada no existe")


def test_integridad_unico_da_409_con_su_mensaje(session, datos):
    e = _violar(session, "INSERT INTO carrera (nombre) VALUES ('TEST Sistemas')")
    assert (e.status_code, e.detail) == (409, "Ya existe una carrera con ese nombre")


def test_integridad_check_da_422_con_su_mensaje(session, datos):
    e = _violar(session, f"UPDATE catedra SET dia_semana = 9 WHERE id = {datos['martes_a'].id}")
    assert (e.status_code, e.detail) == (422, "dia_semana debe estar entre 1 (lunes) y 7 (domingo)")


def test_integridad_restriccion_sin_mensaje_propio_da_422_generico(session, datos):
    e = _violar(session, f"UPDATE carrera SET nombre = NULL WHERE id = {datos['martes_a'].materia.carrera_id}")
    assert (e.status_code, e.detail) == (422, "Los datos violan una restricción de la base")


def test_integridad_al_borrar_da_409(session, datos):
    e = _violar(session, f"DELETE FROM carrera WHERE id = {datos['martes_a'].materia.carrera_id}", al_borrar=True)
    assert (e.status_code, e.detail) == (409, "No se puede borrar: tiene registros asociados")


def test_integridad_deja_la_sesion_usable(session, datos):
    """Después del rollback se puede seguir usando la sesión."""
    _violar(session, "INSERT INTO carrera (nombre) VALUES ('TEST Sistemas')")
    assert session.execute(text("SELECT count(*) FROM carrera WHERE nombre = 'TEST Sistemas'")).scalar() == 1
