"""HU-10: el admin asigna docentes a materias creando y editando cátedras.

Datos de conftest: "Programación II" 1K1 (martes_a) y 1K2 (lunes_a) del docente A,
"Base de Datos" 1K3 (martes_b) del docente B.
"""
from datetime import date, datetime

import pytest

from app.models import Ausencia, Inscripcion
from app.services import ausencias
from tests.conftest import auth

CATEDRAS = "/api/v1/catedras/"
SE_USA = {"detail": "No se puede borrar: tiene registros asociados"}


@pytest.fixture
def admin(datos):
    return auth(datos["u_admin"])


def nueva(datos, **cambios) -> dict:
    return {"materia_id": datos["martes_a"].materia_id, "docente_id": datos["doc_b"].id, "comision": "1K5",
            "dia_semana": 4, "hora_inicio": "14:00", "hora_fin": "16:00", **cambios}


# --- Alta ---------------------------------------------------------------------------------

def test_alta_de_catedra(client, admin, datos):
    r = client.post(CATEDRAS, headers=admin, json=nueva(datos))
    assert r.status_code == 201, r.text
    assert r.json() == {"id": r.json()["id"], "materia_id": datos["martes_a"].materia_id,
                        "docente_id": datos["doc_b"].id, "comision": "1K5", "dia_semana": 4,
                        "hora_inicio": "14:00:00", "hora_fin": "16:00:00"}


def test_materia_y_comision_repetidas_dan_409(client, admin, datos):
    r = client.post(CATEDRAS, headers=admin, json=nueva(datos, comision="1K1"))
    assert r.status_code == 409
    assert r.json() == {"detail": "Esa materia ya tiene una cátedra con esa comisión"}


@pytest.mark.parametrize("cambios, campo", [
    ({"dia_semana": 0}, "dia_semana"),
    ({"dia_semana": 8}, "dia_semana"),
    ({"comision": ""}, "comision"),
    ({"hora_inicio": "25:00"}, "hora_inicio"),
])
def test_validaciones_del_alta_dan_422(client, admin, datos, cambios, campo):
    r = client.post(CATEDRAS, headers=admin, json=nueva(datos, **cambios))
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", campo]


@pytest.mark.parametrize("fin", ["14:00", "13:00"])
def test_hora_fin_no_posterior_da_422(client, admin, datos, fin):
    r = client.post(CATEDRAS, headers=admin, json=nueva(datos, hora_fin=fin))
    assert r.status_code == 422
    assert "hora_fin debe ser posterior a hora_inicio" in r.json()["detail"][0]["msg"]


@pytest.mark.parametrize("campo, mensaje", [
    ("materia_id", "La materia indicada no existe"),
    ("docente_id", "El docente indicado no existe"),
])
def test_materia_o_docente_inexistente_da_422(client, admin, datos, campo, mensaje):
    r = client.post(CATEDRAS, headers=admin, json=nueva(datos, **{campo: 999999999}))
    assert r.status_code == 422
    assert r.json() == {"detail": mensaje}


# --- Consulta y edición ---------------------------------------------------------------

def test_listar_filtrando_por_materia_y_docente(client, admin, datos):
    r = client.get(CATEDRAS, headers=admin, params={"materia_id": datos["martes_a"].materia_id})
    assert [c["id"] for c in r.json()] == [datos["martes_a"].id, datos["lunes_a"].id]
    r = client.get(CATEDRAS, headers=admin, params={"docente_id": datos["doc_b"].id})
    assert [c["id"] for c in r.json()] == [datos["martes_b"].id]


def test_reasignar_la_catedra_a_otro_docente(client, admin, datos, fijar_ahora):
    """Después del PATCH, la próxima clase de la cátedra es del docente nuevo."""
    fijar_ahora(datetime(2026, 11, 2, 10, 0, tzinfo=ausencias.ZONA))
    r = client.patch(f"{CATEDRAS}{datos['martes_a'].id}", headers=admin, json={"docente_id": datos["doc_b"].id})
    assert r.status_code == 200, r.text
    assert r.json()["docente_id"] == datos["doc_b"].id

    def clases(usuario):
        return {c["catedra_id"] for c in client.get("/api/v1/docente/clases-disponibles", headers=auth(usuario)).json()}

    assert datos["martes_a"].id in clases(datos["u_doc_b"])
    assert datos["martes_a"].id not in clases(datos["u_doc_a"])


def test_patch_con_horario_invertido_lo_frena_la_base(client, admin, datos):
    """CatedraUpdate no valida el horario: lo rechaza el CHECK ck_catedra_horario."""
    r = client.patch(f"{CATEDRAS}{datos['martes_a'].id}", headers=admin, json={"hora_fin": "17:00"})
    assert r.status_code == 422
    assert r.json() == {"detail": "hora_fin debe ser posterior a hora_inicio"}


def test_patch_a_comision_repetida_da_409(client, admin, datos):
    r = client.patch(f"{CATEDRAS}{datos['lunes_a'].id}", headers=admin, json={"comision": "1K1"})
    assert r.status_code == 409


def test_patch_con_docente_inexistente_da_422(client, admin, datos):
    r = client.patch(f"{CATEDRAS}{datos['martes_a'].id}", headers=admin, json={"docente_id": 999999999})
    assert r.status_code == 422
    assert r.json() == {"detail": "El docente indicado no existe"}


# --- Borrado ----------------------------------------------------------------------------

def test_borrar_catedra_sin_datos(client, admin, datos):
    catedra_id = client.post(CATEDRAS, headers=admin, json=nueva(datos)).json()["id"]
    assert client.delete(f"{CATEDRAS}{catedra_id}", headers=admin).status_code == 204
    assert client.get(f"{CATEDRAS}{catedra_id}", headers=admin).status_code == 404


def test_borrar_catedra_con_inscripciones_da_409(client, session, admin, datos):
    session.add(Inscripcion(alumno_id=datos["u_alumno"].alumno.id, catedra_id=datos["martes_a"].id))
    session.commit()
    r = client.delete(f"{CATEDRAS}{datos['martes_a'].id}", headers=admin)
    assert r.status_code == 409
    assert r.json() == SE_USA


def test_borrar_catedra_con_avisos_da_409(client, session, admin, datos):
    martes_b = datos["martes_b"]
    session.add(Ausencia(catedra_id=martes_b.id, docente_id=martes_b.docente_id, fecha=date(2026, 11, 3)))
    session.commit()
    r = client.delete(f"{CATEDRAS}{martes_b.id}", headers=admin)
    assert r.status_code == 409
    assert r.json() == SE_USA
    assert client.get(f"{CATEDRAS}{martes_b.id}", headers=admin).status_code == 200


@pytest.mark.parametrize("metodo, cuerpo", [("GET", None), ("PATCH", {"comision": "X"}), ("DELETE", None)])
def test_id_inexistente_da_404(client, admin, metodo, cuerpo):
    r = client.request(metodo, f"{CATEDRAS}999999999", headers=admin, json=cuerpo)
    assert r.status_code == 404
    assert r.json() == {"detail": "Cátedra no encontrada"}


# --- Permisos ----------------------------------------------------------------------------

@pytest.mark.parametrize("quien", ["u_doc_a", "u_alumno"])
def test_solo_el_admin(client, datos, quien):
    assert client.get(CATEDRAS, headers=auth(datos[quien])).status_code == 403
    assert client.post(CATEDRAS, headers=auth(datos[quien]), json=nueva(datos)).status_code == 403
    assert client.delete(f"{CATEDRAS}{datos['martes_a'].id}", headers=auth(datos[quien])).status_code == 403
