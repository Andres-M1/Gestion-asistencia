"""HU-03: el docente ve el historial de sus avisos (pasados y futuros), del más nuevo al más viejo.

Los avisos se crean directo en la base: el POST de HU-02 no permite fechas pasadas.
"""
from datetime import date, datetime, time

import pytest

from app.models import Ausencia, Catedra
from app.services import ausencias
from tests.conftest import auth

AVISOS = "/api/v1/docente/avisos"


def _aviso(session, catedra, fecha):
    aviso = Ausencia(catedra_id=catedra.id, docente_id=catedra.docente_id, fecha=fecha)
    session.add(aviso)
    session.commit()
    return aviso


@pytest.fixture
def avisos(session, datos):
    """Docente A: 4 avisos (uno pasado, dos el mismo día). Docente B: 1 aviso."""
    temprano_a = Catedra(materia_id=datos["martes_a"].materia_id, docente_id=datos["doc_a"].id,
                         comision="1K9", dia_semana=2, hora_inicio=time(8, 0), hora_fin=time(10, 0))
    session.add(temprano_a)
    session.commit()
    return {
        "pasado": _aviso(session, datos["lunes_a"], date(2026, 10, 26)),
        "martes_18hs": _aviso(session, datos["martes_a"], date(2026, 11, 3)),
        "martes_8hs": _aviso(session, temprano_a, date(2026, 11, 3)),
        "futuro": _aviso(session, datos["lunes_a"], date(2026, 11, 9)),
        "de_otro_docente": _aviso(session, datos["martes_b"], date(2026, 11, 3)),
    }


def mis_avisos(client, usuario, **params):
    r = client.get(AVISOS, headers=auth(usuario), params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_un_docente_no_ve_avisos_de_otro(client, datos, avisos):
    ids_a = {a["id"] for a in mis_avisos(client, datos["u_doc_a"])}
    ids_b = {a["id"] for a in mis_avisos(client, datos["u_doc_b"])}
    assert avisos["de_otro_docente"].id not in ids_a
    assert ids_b == {avisos["de_otro_docente"].id}


def test_incluye_pasados_y_futuros_ordenados_por_fecha_descendente(client, datos, avisos):
    ids = [a["id"] for a in mis_avisos(client, datos["u_doc_a"])]
    # Mismo día (03/11): primero la clase de las 18:00, después la de las 8:00
    assert ids == [avisos[k].id for k in ("futuro", "martes_18hs", "martes_8hs", "pasado")]


def test_cada_aviso_trae_el_detalle_sin_estado(client, datos, avisos):
    pasado = mis_avisos(client, datos["u_doc_a"])[-1]
    assert pasado.pop("creado_en")
    assert pasado == {
        "id": avisos["pasado"].id, "fecha": "2026-10-26", "materia": "Programación II", "comision": "1K2",
        "dia_semana": 1, "hora_inicio": "18:00:00", "hora_fin": "20:00:00",
        "docente": {"nombre": "Doc", "apellido": "80000001"},
    }


def test_paginacion(client, datos, avisos):
    pagina = mis_avisos(client, datos["u_doc_a"], offset=1, limit=1)
    assert [a["id"] for a in pagina] == [avisos["martes_18hs"].id]
    assert client.get(AVISOS, headers=auth(datos["u_doc_a"]), params={"limit": 101}).status_code == 422


def test_docente_sin_avisos_recibe_lista_vacia(client, datos):
    assert mis_avisos(client, datos["u_doc_a"]) == []


@pytest.mark.parametrize("quien", ["u_alumno", "u_admin", "u_docente_sin_perfil"])
def test_solo_docentes_con_perfil(client, datos, quien):
    assert client.get(AVISOS, headers=auth(datos[quien])).status_code == 403


def test_sin_token_responde_401(client):
    assert client.get(AVISOS).status_code == 401


def test_al_reasignar_la_catedra_los_avisos_anteriores_siguen_siendo_de_quien_los_dio(
    client, datos, avisos, fijar_ahora
):
    """lunes_a (docente A) pasa al docente B: los avisos que dio A siguen en su historial
    y a su nombre; B no los ve, y los avisos que B dé desde ahora son de B."""
    r = client.patch(f"/api/v1/catedras/{datos['lunes_a'].id}", headers=auth(datos["u_admin"]),
                     json={"docente_id": datos["doc_b"].id})
    assert r.status_code == 200, r.text

    fijar_ahora(datetime(2026, 11, 10, 10, 0, tzinfo=ausencias.ZONA))
    r = client.post(AVISOS, headers=auth(datos["u_doc_b"]),
                    json={"catedra_id": datos["lunes_a"].id, "fecha": "2026-11-16"})
    assert r.status_code == 201, r.text
    nuevo_de_b = r.json()["id"]

    de_a = mis_avisos(client, datos["u_doc_a"])
    assert [a["id"] for a in de_a] == [avisos[k].id for k in ("futuro", "martes_18hs", "martes_8hs", "pasado")]
    assert {a["docente"]["apellido"] for a in de_a} == {"80000001"}

    de_b = mis_avisos(client, datos["u_doc_b"])
    assert [a["id"] for a in de_b] == [nuevo_de_b, avisos["de_otro_docente"].id]
    assert {a["docente"]["apellido"] for a in de_b} == {"80000002"}
