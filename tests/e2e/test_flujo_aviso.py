"""E2E: flujo completo de un aviso (HU-01, HU-02, HU-03, HU-05, HU-07, HU-09).

El docente toma una clase de su lista (sin fechas fijas) y registra el aviso. Después
se comprueba lo que ve cada rol. Los alumnos inscriptos y no inscriptos en esa cátedra
se averiguan con /alumno/inscripciones, no se asumen.
"""
from datetime import date, timedelta

import pytest

from tests.e2e.conftest import ADMIN, ALUMNOS, DOCENTE, OTRO_DOCENTE

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def clase(api, login):
    r = api.get("/docente/clases-disponibles", headers=login(DOCENTE))
    assert r.status_code == 200, r.text
    assert r.json(), "El docente no tiene clases disponibles en los próximos 7 días"
    return r.json()[0]


@pytest.fixture(scope="module")
def aviso(api, login, clase):
    r = api.post("/docente/avisos", headers=login(DOCENTE),
                 json={"catedra_id": clase["catedra_id"], "fecha": clase["fecha"]})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def alumnos(api, login, clase):
    """(inscriptos, no_inscriptos) en la cátedra de la clase, con inscripción vigente."""
    inscriptos, no_inscriptos = [], []
    for dni in ALUMNOS:
        r = api.get("/alumno/inscripciones", headers=login(dni))
        assert r.status_code == 200, r.text
        catedras = {i["catedra_id"] for i in r.json()}
        (inscriptos if clase["catedra_id"] in catedras else no_inscriptos).append(dni)
    assert inscriptos and no_inscriptos, "Los datos de prueba deberían tener de los dos"
    return inscriptos, no_inscriptos


def ids(respuesta) -> list[int]:
    assert respuesta.status_code == 200, respuesta.text
    return [a["id"] for a in respuesta.json()]


# --- HU-01 ------------------------------------------------------------------------

@pytest.mark.parametrize("dni, rol, con_perfil", [
    (ADMIN, "admin", False), (DOCENTE, "docente", True), (ALUMNOS[0], "estudiante", True),
])
def test_login_por_rol(api, login, dni, rol, con_perfil):
    r = api.get("/auth/me", headers=login(dni))
    assert r.status_code == 200, r.text
    assert r.json()["dni"] == dni
    assert r.json()["rol"] == rol
    assert (r.json()["perfil"] is not None) == con_perfil


# --- HU-02 y HU-03: docente -----------------------------------------------------------

def test_registrar_aviso_devuelve_el_detalle_de_la_clase(aviso, clase):
    for campo in ("fecha", "materia", "comision", "dia_semana", "hora_inicio", "hora_fin"):
        assert aviso[campo] == clase[campo]
    assert aviso["docente"] == {"nombre": "Laura", "apellido": "Gómez"}
    assert "estado" not in aviso


def test_la_clase_avisada_sale_de_la_lista(api, login, aviso, clase):
    r = api.get("/docente/clases-disponibles", headers=login(DOCENTE))
    assert r.status_code == 200, r.text
    assert (clase["catedra_id"], clase["fecha"]) not in {(c["catedra_id"], c["fecha"]) for c in r.json()}


def test_el_aviso_duplicado_da_409(api, login, aviso, clase):
    r = api.post("/docente/avisos", headers=login(DOCENTE),
                 json={"catedra_id": clase["catedra_id"], "fecha": clase["fecha"]})
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya hay un aviso para esa cátedra en esa fecha"}


def test_el_aviso_esta_en_el_historial_del_docente_y_no_en_el_de_otro(api, login, aviso):
    assert aviso["id"] in ids(api.get("/docente/avisos", headers=login(DOCENTE)))
    assert aviso["id"] not in ids(api.get("/docente/avisos", headers=login(OTRO_DOCENTE)))


# --- HU-05 y HU-07: alumno ----------------------------------------------------------

def test_el_alumno_inscripto_ve_el_aviso(api, login, aviso, clase, alumnos):
    inscriptos, _ = alumnos
    for dni in inscriptos:
        assert aviso["id"] in ids(api.get("/alumno/avisos", headers=login(dni)))
        assert aviso["id"] in ids(api.get("/alumno/avisos", headers=login(dni),
                                          params={"catedra_id": clase["catedra_id"]}))


def test_el_alumno_no_inscripto_no_ve_el_aviso(api, login, aviso, clase, alumnos):
    _, no_inscriptos = alumnos
    for dni in no_inscriptos:
        assert aviso["id"] not in ids(api.get("/alumno/avisos", headers=login(dni)))
        r = api.get("/alumno/avisos", headers=login(dni), params={"catedra_id": clase["catedra_id"]})
        assert r.status_code == 404
        assert r.json() == {"detail": "No tenés una inscripción vigente en esa cátedra"}


# --- HU-09: admin --------------------------------------------------------------------

def test_el_admin_encuentra_el_aviso_con_filtros(api, login, aviso):
    docente_id = api.get("/auth/me", headers=login(DOCENTE)).json()["perfil"]["id"]
    filtros = {
        "docente_id": docente_id,
        "comision": aviso["comision"].lower(),  # sin distinguir mayúsculas
        "fecha_desde": aviso["fecha"],
        "fecha_hasta": aviso["fecha"],
    }
    assert aviso["id"] in ids(api.get("/admin/avisos", headers=login(ADMIN), params=filtros))

    dia_siguiente = (date.fromisoformat(aviso["fecha"]) + timedelta(days=1)).isoformat()
    sin_el_aviso = {**filtros, "fecha_desde": dia_siguiente, "fecha_hasta": dia_siguiente}
    assert aviso["id"] not in ids(api.get("/admin/avisos", headers=login(ADMIN), params=sin_el_aviso))
