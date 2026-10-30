"""E2E: respuestas de error 401, 403, 404 y 422 (ver docs/api.md).

Ningún request de este archivo crea datos: todos los avisos que se intentan son inválidos.
"""
from datetime import date, timedelta

import pytest

from tests.e2e.conftest import ADMIN, ALUMNOS, DOCENTE, OTRO_DOCENTE, PASSWORD

pytestmark = pytest.mark.e2e

ALUMNO = ALUMNOS[0]


def mover(fecha: str, dias: int) -> str:
    return (date.fromisoformat(fecha) + timedelta(days=dias)).isoformat()


@pytest.fixture(scope="module")
def clase(api, login):
    r = api.get("/docente/clases-disponibles", headers=login(DOCENTE))
    assert r.status_code == 200 and r.json(), r.text
    return r.json()[0]


# --- 401 ---------------------------------------------------------------------------

@pytest.mark.parametrize("dni, password", [(DOCENTE, "incorrecta"), ("99999999", PASSWORD)])
def test_login_incorrecto_da_401_con_el_mismo_mensaje(api, dni, password):
    r = api.post("/auth/login", json={"dni": dni, "password": password})
    assert r.status_code == 401
    assert r.json() == {"detail": "DNI o contraseña incorrectos"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_sin_token_da_401(api):
    r = api.get("/docente/avisos")
    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


def test_token_invalido_da_401(api):
    r = api.get("/auth/me", headers={"Authorization": "Bearer token-inventado"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Token inválido o expirado"}


# --- 403 ---------------------------------------------------------------------------

@pytest.mark.parametrize("dni, metodo, ruta", [
    (ALUMNO, "GET", "/docente/clases-disponibles"),
    (ALUMNO, "GET", "/docentes/"),
    (DOCENTE, "GET", "/alumno/avisos"),
    (DOCENTE, "GET", "/admin/avisos"),
    (ADMIN, "GET", "/docente/avisos"),
    (ADMIN, "DELETE", "/auth/me/fcm-token"),
])
def test_rol_equivocado_da_403(api, login, dni, metodo, ruta):
    r = api.request(metodo, ruta, headers=login(dni))
    assert r.status_code == 403
    assert r.json() == {"detail": "No tenés permiso para esta acción"}


# --- Registrar aviso: 404 y 422 de negocio ------------------------------------------

def test_catedra_de_otro_docente_da_404(api, login):
    ajena = api.get("/docente/clases-disponibles", headers=login(OTRO_DOCENTE)).json()[0]
    r = api.post("/docente/avisos", headers=login(DOCENTE),
                 json={"catedra_id": ajena["catedra_id"], "fecha": ajena["fecha"]})
    assert r.status_code == 404
    assert r.json() == {"detail": "Cátedra no encontrada"}


@pytest.mark.parametrize("dias, mensaje", [
    (1, "La fecha no corresponde al día de cursada de la cátedra"),
    (7, "Solo se puede avisar sobre clases de los próximos 7 días"),
    (-7, "Solo se puede avisar hasta 1 hora antes del inicio de la clase"),
])
def test_fecha_invalida_da_422(api, login, clase, dias, mensaje):
    r = api.post("/docente/avisos", headers=login(DOCENTE),
                 json={"catedra_id": clase["catedra_id"], "fecha": mover(clase["fecha"], dias)})
    assert r.status_code == 422
    assert r.json() == {"detail": mensaje}


# --- 422 de validación ----------------------------------------------------------------

def test_body_incompleto_da_422_con_el_campo(api, login, clase):
    r = api.post("/docente/avisos", headers=login(DOCENTE), json={"catedra_id": clase["catedra_id"]})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "fecha"]


def test_limit_mayor_a_100_da_422(api, login):
    r = api.get("/docente/avisos", headers=login(DOCENTE), params={"limit": 101})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "limit"]


def test_rango_de_fechas_invertido_da_422(api, login):
    r = api.get("/admin/avisos", headers=login(ADMIN),
                params={"fecha_desde": "2026-11-10", "fecha_hasta": "2026-11-01"})
    assert r.status_code == 422
    assert r.json() == {"detail": "fecha_desde no puede ser posterior a fecha_hasta"}


def test_token_fcm_vacio_da_422(api, login):
    r = api.put("/auth/me/fcm-token", headers=login(ALUMNO), json={"token": ""})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "token"]


# --- 404 del alumno ----------------------------------------------------------------

def test_alumno_con_catedra_inexistente_da_404(api, login):
    r = api.get("/alumno/avisos", headers=login(ALUMNO), params={"catedra_id": 999999})
    assert r.status_code == 404
    assert r.json() == {"detail": "No tenés una inscripción vigente en esa cátedra"}
