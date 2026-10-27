"""HU-09: el admin lista todos los avisos con filtros combinables.

Escenario (además de conftest): una segunda carrera "TEST Industrial" con la materia
"Física", comisión 1K1, martes 08:00, dictada por el docente B.

Avisos, en el orden esperado (fecha desc, hora_inicio desc, id desc):
  futuro   lunes_a   (Prog. II 1K2, doc A)  09/11
  b_1803   martes_b  (BD 1K3, doc B)        03/11 18:00  ┐ misma fecha y hora:
  a_1803   martes_a  (Prog. II 1K1, doc A)  03/11 18:00  ┘ desempata el id
  fisica   física    (Física 1K1, doc B)    03/11 08:00
  lunes    lunes_a   (Prog. II 1K2, doc A)  02/11
  pasado   martes_a  (Prog. II 1K1, doc A)  27/10
"""
from datetime import date, time

import pytest

from sqlmodel import delete

from app.models import Ausencia, Carrera, Catedra, Materia
from tests.conftest import auth

AVISOS = "/api/v1/admin/avisos"
ORDEN = ["futuro", "b_1803", "a_1803", "fisica", "lunes", "pasado"]


def _guardar(session, objeto):
    session.add(objeto)
    session.commit()
    return objeto


@pytest.fixture
def esc(session, datos):
    # El admin ve TODOS los avisos y los tests corren contra la base de desarrollo:
    # se vacía la tabla dentro de la transacción del test (que se revierte al final),
    # así los avisos cargados a mano no cambian los resultados y no se pierden.
    session.exec(delete(Ausencia))
    session.commit()
    industrial = _guardar(session, Carrera(nombre="TEST Industrial"))
    fisica = _guardar(session, Materia(carrera_id=industrial.id, nombre="Física"))
    cat_fisica = _guardar(session, Catedra(materia_id=fisica.id, docente_id=datos["doc_b"].id, comision="1K1",
                                           dia_semana=2, hora_inicio=time(8, 0), hora_fin=time(10, 0)))

    def aviso(catedra, fecha):
        return _guardar(session, Ausencia(catedra_id=catedra.id, fecha=fecha))

    # a_1803 se crea antes que b_1803, así b_1803 tiene id mayor y va primero
    return {
        "industrial": industrial, "sistemas_id": datos["martes_a"].materia.carrera_id,
        "prog_id": datos["martes_a"].materia_id,
        "pasado": aviso(datos["martes_a"], date(2026, 10, 27)),
        "lunes": aviso(datos["lunes_a"], date(2026, 11, 2)),
        "a_1803": aviso(datos["martes_a"], date(2026, 11, 3)),
        "b_1803": aviso(datos["martes_b"], date(2026, 11, 3)),
        "fisica": aviso(cat_fisica, date(2026, 11, 3)),
        "futuro": aviso(datos["lunes_a"], date(2026, 11, 9)),
    }


def avisos(client, datos, **filtros):
    r = client.get(AVISOS, headers=auth(datos["u_admin"]), params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def nombres(esc, respuesta):
    por_id = {esc[k].id: k for k in ORDEN}
    return [por_id[a["id"]] for a in respuesta]


# --- Sin filtros ------------------------------------------------------------------

def test_incluye_pasados_y_futuros_por_fecha_descendente_con_desempate(client, datos, esc):
    assert nombres(esc, avisos(client, datos)) == ORDEN


def test_cada_aviso_trae_el_detalle(client, datos, esc):
    fisica = next(a for a in avisos(client, datos) if a["id"] == esc["fisica"].id)
    assert fisica.pop("creado_en")
    assert fisica == {
        "id": esc["fisica"].id, "fecha": "2026-11-03", "materia": "Física", "comision": "1K1",
        "dia_semana": 2, "hora_inicio": "08:00:00", "hora_fin": "10:00:00",
        "docente": {"nombre": "Doc", "apellido": "80000002"},
    }


# --- Cada filtro por separado -----------------------------------------------------

def test_filtro_carrera(client, datos, esc):
    assert nombres(esc, avisos(client, datos, carrera_id=esc["industrial"].id)) == ["fisica"]
    assert nombres(esc, avisos(client, datos, carrera_id=esc["sistemas_id"])) == [k for k in ORDEN if k != "fisica"]


def test_filtro_materia(client, datos, esc):
    assert nombres(esc, avisos(client, datos, materia_id=esc["prog_id"])) == ["futuro", "a_1803", "lunes", "pasado"]


@pytest.mark.parametrize("texto", ["1K1", "1k1"])
def test_filtro_comision_exacta_sin_distinguir_mayusculas(client, datos, esc, texto):
    # 1K1 existe en Programación II (doc A) y en Física (doc B)
    assert nombres(esc, avisos(client, datos, comision=texto)) == ["a_1803", "fisica", "pasado"]


def test_filtro_comision_no_busca_texto_parcial(client, datos, esc):
    assert avisos(client, datos, comision="1K") == []
    assert avisos(client, datos, comision="1K%") == []


def test_filtro_docente(client, datos, esc):
    assert nombres(esc, avisos(client, datos, docente_id=datos["doc_b"].id)) == ["b_1803", "fisica"]


def test_filtro_fecha_desde(client, datos, esc):
    assert nombres(esc, avisos(client, datos, fecha_desde="2026-11-03")) == ["futuro", "b_1803", "a_1803", "fisica"]


def test_filtro_fecha_hasta(client, datos, esc):
    assert nombres(esc, avisos(client, datos, fecha_hasta="2026-11-02")) == ["lunes", "pasado"]


# --- Combinaciones y rango ----------------------------------------------------------

def test_dos_filtros_combinados(client, datos, esc):
    assert nombres(esc, avisos(client, datos, docente_id=datos["doc_a"].id, fecha_desde="2026-11-02")) == [
        "futuro", "a_1803", "lunes",
    ]
    assert nombres(esc, avisos(client, datos, materia_id=esc["prog_id"], comision="1k2")) == ["futuro", "lunes"]


def test_el_rango_de_fechas_incluye_los_extremos(client, datos, esc):
    assert nombres(esc, avisos(client, datos, fecha_desde="2026-11-02", fecha_hasta="2026-11-03")) == [
        "b_1803", "a_1803", "fisica", "lunes",
    ]
    assert nombres(esc, avisos(client, datos, fecha_desde="2026-11-02", fecha_hasta="2026-11-02")) == ["lunes"]


def test_rango_invertido_da_422(client, datos, esc):
    r = client.get(AVISOS, headers=auth(datos["u_admin"]),
                   params={"fecha_desde": "2026-11-04", "fecha_hasta": "2026-11-03"})
    assert r.status_code == 422
    assert r.json()["detail"] == "fecha_desde no puede ser posterior a fecha_hasta"


def test_ids_inexistentes_devuelven_lista_vacia(client, datos, esc):
    assert avisos(client, datos, carrera_id=999999) == []
    assert avisos(client, datos, docente_id=999999) == []


def test_paginacion(client, datos, esc):
    assert nombres(esc, avisos(client, datos, offset=1, limit=2)) == ["b_1803", "a_1803"]
    assert client.get(AVISOS, headers=auth(datos["u_admin"]), params={"limit": 101}).status_code == 422


# --- Permisos ---------------------------------------------------------------------

@pytest.mark.parametrize("quien", ["u_doc_a", "u_alumno"])
def test_docente_o_alumno_reciben_403(client, datos, quien):
    assert client.get(AVISOS, headers=auth(datos[quien])).status_code == 403


def test_sin_token_responde_401(client):
    assert client.get(AVISOS).status_code == 401
