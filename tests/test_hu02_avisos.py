"""HU-02: el docente registra un aviso eligiendo una clase concreta de una lista.

Hora de referencia: lunes 02/11/2026 10:00 (Argentina). Con los datos de conftest,
el docente A tiene clases el lunes 02/11 18:00 (1K2) y el martes 03/11 18:00 (1K1).
"""
from datetime import datetime, timezone

import pytest

from app.models.ausencia import Ausencia, EstadoAusencia
from app.services import ausencias
from tests.conftest import auth

AR = ausencias.ZONA
CLASES = "/api/v1/docente/clases-disponibles"
AVISOS = "/api/v1/docente/avisos"


@pytest.fixture(autouse=True)
def lunes_10hs(fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 10, 0, tzinfo=AR))


def clases(client, usuario):
    r = client.get(CLASES, headers=auth(usuario))
    assert r.status_code == 200, r.text
    return [(c["catedra_id"], c["fecha"]) for c in r.json()]


def avisar(client, usuario, catedra, fecha):
    return client.post(AVISOS, headers=auth(usuario), json={"catedra_id": catedra.id, "fecha": fecha})


# --- Lista de clases disponibles -------------------------------------------------

def test_lista_las_clases_del_docente_de_los_proximos_7_dias(client, datos):
    # El lunes 09/11 18:00 queda fuera: está a 7 días y 8 horas
    assert clases(client, datos["u_doc_a"]) == [
        (datos["lunes_a"].id, "2026-11-02"),
        (datos["martes_a"].id, "2026-11-03"),
    ]


def test_cada_opcion_trae_materia_comision_dia_y_horario(client, datos):
    primera = client.get(CLASES, headers=auth(datos["u_doc_a"])).json()[0]
    assert primera == {
        "catedra_id": datos["lunes_a"].id, "fecha": "2026-11-02", "materia": "Programación II",
        "comision": "1K2", "dia_semana": 1, "hora_inicio": "18:00:00", "hora_fin": "20:00:00",
    }


def test_no_lista_catedras_de_otro_docente(client, datos):
    ids = {catedra_id for catedra_id, _ in clases(client, datos["u_doc_a"])}
    assert datos["martes_b"].id not in ids


def test_una_hora_antes_exacta_todavia_aparece(client, datos, fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 17, 0, tzinfo=AR))
    assert (datos["lunes_a"].id, "2026-11-02") in clases(client, datos["u_doc_a"])


def test_a_menos_de_una_hora_ya_no_aparece(client, datos, fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 17, 1, tzinfo=AR))
    assert (datos["lunes_a"].id, "2026-11-02") not in clases(client, datos["u_doc_a"])


def test_clase_justo_a_7_dias_aparece(client, datos, fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 18, 0, tzinfo=AR))
    assert (datos["lunes_a"].id, "2026-11-09") in clases(client, datos["u_doc_a"])


def test_clase_con_aviso_no_aparece(client, datos):
    assert avisar(client, datos["u_doc_a"], datos["martes_a"], "2026-11-03").status_code == 201
    assert (datos["martes_a"].id, "2026-11-03") not in clases(client, datos["u_doc_a"])


def test_docente_sin_catedras_recibe_lista_vacia(client, datos, session):
    for catedra in (datos["martes_a"], datos["lunes_a"]):
        session.delete(catedra)
    session.commit()
    assert clases(client, datos["u_doc_a"]) == []


# --- Registrar aviso ---------------------------------------------------------------

def test_registra_aviso_en_estado_activo_y_devuelve_el_detalle(client, datos, session):
    r = avisar(client, datos["u_doc_a"], datos["martes_a"], "2026-11-03")
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo.pop("creado_en")
    assert cuerpo == {
        "id": cuerpo["id"], "fecha": "2026-11-03", "materia": "Programación II", "comision": "1K1",
        "dia_semana": 2, "hora_inicio": "18:00:00", "hora_fin": "20:00:00",
        "docente": {"nombre": "Doc", "apellido": "80000001"},
    }
    guardado = session.get(Ausencia, cuerpo["id"])
    assert guardado.estado == EstadoAusencia.activo
    assert guardado.docente_id == datos["doc_a"].id


def test_no_permite_dos_avisos_para_la_misma_clase(client, datos):
    avisar(client, datos["u_doc_a"], datos["martes_a"], "2026-11-03")
    r = avisar(client, datos["u_doc_a"], datos["martes_a"], "2026-11-03")
    assert r.status_code == 409
    assert r.json()["detail"] == "Ya hay un aviso para esa cátedra en esa fecha"


def test_rechaza_catedra_de_otro_docente(client, datos):
    r = avisar(client, datos["u_doc_a"], datos["martes_b"], "2026-11-03")
    assert r.status_code == 404


def test_rechaza_catedra_inexistente(client, datos):
    r = client.post(AVISOS, headers=auth(datos["u_doc_a"]), json={"catedra_id": 999999, "fecha": "2026-11-03"})
    assert r.status_code == 404


def test_rechaza_fecha_que_no_es_dia_de_cursada(client, datos):
    r = avisar(client, datos["u_doc_a"], datos["martes_a"], "2026-11-04")  # miércoles
    assert r.status_code == 422
    assert "día de cursada" in r.json()["detail"]


def test_rechaza_a_menos_de_una_hora(client, datos, fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 17, 30, tzinfo=AR))
    r = avisar(client, datos["u_doc_a"], datos["lunes_a"], "2026-11-02")
    assert r.status_code == 422
    assert "1 hora" in r.json()["detail"]


def test_rechaza_fecha_pasada(client, datos):
    r = avisar(client, datos["u_doc_a"], datos["lunes_a"], "2026-10-26")
    assert r.status_code == 422


def test_rechaza_fuera_de_la_ventana_de_7_dias(client, datos):
    r = avisar(client, datos["u_doc_a"], datos["lunes_a"], "2026-11-09")  # a 7 días y 8 horas
    assert r.status_code == 422
    assert "7 días" in r.json()["detail"]


def test_compara_en_hora_argentina_aunque_el_servidor_este_en_utc(client, datos, fijar_ahora):
    # 19:00 UTC = 16:00 en Argentina: la clase de las 18:00 está a 2 horas, así que se acepta.
    # Si se comparara con la hora UTC, 18:00 ya habría pasado.
    fijar_ahora(datetime(2026, 11, 3, 19, 0, tzinfo=timezone.utc))
    assert avisar(client, datos["u_doc_a"], datos["martes_a"], "2026-11-03").status_code == 201


def test_ahora_devuelve_hora_argentina():
    assert ausencias.ahora().utcoffset() == datetime(2026, 1, 1, tzinfo=AR).utcoffset()


# --- Permisos ---------------------------------------------------------------------

@pytest.mark.parametrize("ruta", [CLASES, AVISOS])
def test_sin_token_responde_401(client, ruta):
    r = client.get(ruta) if ruta == CLASES else client.post(ruta, json={"catedra_id": 1, "fecha": "2026-11-03"})
    assert r.status_code == 401


@pytest.mark.parametrize("quien", ["u_alumno", "u_admin"])
def test_solo_docentes(client, datos, quien):
    assert client.get(CLASES, headers=auth(datos[quien])).status_code == 403
    assert avisar(client, datos[quien], datos["martes_a"], "2026-11-03").status_code == 403


def test_docente_sin_perfil_responde_403(client, datos):
    assert client.get(CLASES, headers=auth(datos["u_docente_sin_perfil"])).status_code == 403
