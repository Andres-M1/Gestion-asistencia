"""HU-07: el alumno ve sus inscripciones vigentes.
HU-05: el alumno ve los avisos de hoy en adelante de las cátedras donde tiene inscripción vigente.

Hoy (fijado): lunes 02/11/2026 10:00, hora de Argentina.
El alumno de conftest queda inscripto así:
  - "Programación II" 1K1, martes 18:00 (docente A): vigente
  - "Programación II" 1K9, martes 08:00 (docente A): vigente
  - "Programación II" 1K2, lunes 18:00 (docente A): NO vigente
  - "Base de Datos" 1K3, martes 18:00 (docente B): sin inscripción
"""
from datetime import date, datetime, time

import pytest

from app.models import Alumno, Ausencia, Catedra, Inscripcion, Usuario
from app.models.usuario import Rol
from app.services import ausencias
from tests.conftest import auth

AR = ausencias.ZONA
INSCRIPCIONES = "/api/v1/alumno/inscripciones"
AVISOS = "/api/v1/alumno/avisos"


@pytest.fixture(autouse=True)
def lunes_10hs(fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 10, 0, tzinfo=AR))


def _guardar(session, *objetos):
    session.add_all(objetos)
    session.commit()
    return objetos


@pytest.fixture
def escenario(session, datos):
    alumno = datos["u_alumno"].alumno
    temprano_a = Catedra(materia_id=datos["martes_a"].materia_id, docente_id=datos["doc_a"].id,
                         comision="1K9", dia_semana=2, hora_inicio=time(8, 0), hora_fin=time(10, 0))
    _guardar(session, temprano_a)
    _guardar(
        session,
        Inscripcion(alumno_id=alumno.id, catedra_id=datos["martes_a"].id, vigente=True),
        Inscripcion(alumno_id=alumno.id, catedra_id=temprano_a.id, vigente=True),
        Inscripcion(alumno_id=alumno.id, catedra_id=datos["lunes_a"].id, vigente=False),
    )

    def aviso(catedra, fecha):
        return _guardar(session, Ausencia(catedra_id=catedra.id, docente_id=catedra.docente_id, fecha=fecha))[0]

    return {
        "alumno": alumno,
        "temprano_a": temprano_a,
        "pasado": aviso(datos["martes_a"], date(2026, 10, 27)),
        "martes_18hs": aviso(datos["martes_a"], date(2026, 11, 3)),
        "martes_8hs": aviso(temprano_a, date(2026, 11, 3)),
        "martes_siguiente": aviso(datos["martes_a"], date(2026, 11, 10)),
        "no_vigente_hoy": aviso(datos["lunes_a"], date(2026, 11, 2)),
        "no_vigente_futuro": aviso(datos["lunes_a"], date(2026, 11, 9)),
        "sin_inscripcion": aviso(datos["martes_b"], date(2026, 11, 3)),
    }


def get(client, usuario, ruta, **params):
    r = client.get(ruta, headers=auth(usuario), params=params)
    assert r.status_code == 200, r.text
    return r.json()


def ids(avisos):
    return [a["id"] for a in avisos]


# --- HU-07: inscripciones vigentes ------------------------------------------------

def test_hu07_lista_solo_inscripciones_vigentes_en_orden_de_la_semana(client, datos, escenario):
    lista = get(client, datos["u_alumno"], INSCRIPCIONES)
    assert [i["catedra_id"] for i in lista] == [escenario["temprano_a"].id, datos["martes_a"].id]


def test_hu07_cada_item_trae_materia_comision_horario_y_docente(client, datos, escenario):
    item = get(client, datos["u_alumno"], INSCRIPCIONES)[1]
    assert item == {
        "catedra_id": datos["martes_a"].id, "materia": "Programación II", "comision": "1K1",
        "dia_semana": 2, "hora_inicio": "18:00:00", "hora_fin": "20:00:00",
        "docente": {"nombre": "Doc", "apellido": "80000001"},
    }


def test_hu07_no_ve_inscripciones_de_otro_alumno(client, datos, escenario, session):
    otro_usuario, = _guardar(session, Usuario(dni="80000009", password_hash="x", rol=Rol.estudiante))
    otro, = _guardar(session, Alumno(usuario_id=otro_usuario.id, carrera_id=escenario["alumno"].carrera_id,
                                     nombre="Otro", apellido="Alumno", email="otro@gestion-test.com.ar"))
    _guardar(session, Inscripcion(alumno_id=otro.id, catedra_id=datos["martes_b"].id))
    assert [i["catedra_id"] for i in get(client, otro_usuario, INSCRIPCIONES)] == [datos["martes_b"].id]
    assert datos["martes_b"].id not in [i["catedra_id"] for i in get(client, datos["u_alumno"], INSCRIPCIONES)]


def test_hu07_alumno_sin_inscripciones_recibe_lista_vacia(client, datos):
    assert get(client, datos["u_alumno"], INSCRIPCIONES) == []


# --- HU-05: avisos de mis cátedras ----------------------------------------------

def test_hu05_solo_avisos_futuros_de_inscripciones_vigentes_en_orden_ascendente(client, datos, escenario):
    # Mismo día (03/11): primero la clase de las 8:00, después la de las 18:00
    assert ids(get(client, datos["u_alumno"], AVISOS)) == [
        escenario[k].id for k in ("martes_8hs", "martes_18hs", "martes_siguiente")
    ]


def test_hu05_no_ve_avisos_de_catedras_donde_no_esta_inscripto(client, datos, escenario):
    assert escenario["sin_inscripcion"].id not in ids(get(client, datos["u_alumno"], AVISOS))


def test_hu05_no_ve_avisos_de_una_inscripcion_no_vigente(client, datos, escenario):
    vistos = ids(get(client, datos["u_alumno"], AVISOS))
    assert escenario["no_vigente_hoy"].id not in vistos
    assert escenario["no_vigente_futuro"].id not in vistos


def test_hu05_no_ve_avisos_pasados(client, datos, escenario):
    assert escenario["pasado"].id not in ids(get(client, datos["u_alumno"], AVISOS))


def test_hu05_ve_el_aviso_de_hoy_aunque_la_clase_ya_haya_terminado(client, datos, escenario, fijar_ahora):
    fijar_ahora(datetime(2026, 11, 3, 22, 0, tzinfo=AR))  # martes 03/11, después de las dos clases
    assert ids(get(client, datos["u_alumno"], AVISOS))[:2] == [escenario["martes_8hs"].id, escenario["martes_18hs"].id]
    fijar_ahora(datetime(2026, 11, 4, 0, 30, tzinfo=AR))  # al día siguiente ya no
    assert ids(get(client, datos["u_alumno"], AVISOS)) == [escenario["martes_siguiente"].id]


def test_hu05_trae_el_detalle_del_aviso(client, datos, escenario):
    aviso = get(client, datos["u_alumno"], AVISOS)[0]
    assert aviso.pop("creado_en")
    assert aviso == {
        "id": escenario["martes_8hs"].id, "fecha": "2026-11-03", "materia": "Programación II", "comision": "1K9",
        "dia_semana": 2, "hora_inicio": "08:00:00", "hora_fin": "10:00:00",
        "docente": {"nombre": "Doc", "apellido": "80000001"},
    }


def test_hu05_filtro_catedra_id(client, datos, escenario):
    filtrados = get(client, datos["u_alumno"], AVISOS, catedra_id=datos["martes_a"].id)
    assert ids(filtrados) == [escenario["martes_18hs"].id, escenario["martes_siguiente"].id]


@pytest.mark.parametrize("catedra", ["martes_b", "lunes_a"])  # sin inscripción / inscripción no vigente
def test_hu05_filtro_catedra_id_da_404_si_no_esta_inscripto(client, datos, escenario, catedra):
    r = client.get(AVISOS, headers=auth(datos["u_alumno"]), params={"catedra_id": datos[catedra].id})
    assert r.status_code == 404
    assert r.json()["detail"] == "No tenés una inscripción vigente en esa cátedra"


def test_hu05_filtro_con_catedra_inexistente_da_404(client, datos, escenario):
    r = client.get(AVISOS, headers=auth(datos["u_alumno"]), params={"catedra_id": 999999})
    assert r.status_code == 404


def test_hu05_paginacion(client, datos, escenario):
    assert ids(get(client, datos["u_alumno"], AVISOS, offset=1, limit=1)) == [escenario["martes_18hs"].id]
    assert client.get(AVISOS, headers=auth(datos["u_alumno"]), params={"limit": 101}).status_code == 422


# --- Permisos (las dos HU) ------------------------------------------------------

@pytest.mark.parametrize("ruta", [INSCRIPCIONES, AVISOS])
@pytest.mark.parametrize("quien", ["u_doc_a", "u_admin"])
def test_docente_o_admin_reciben_403(client, datos, ruta, quien):
    assert client.get(ruta, headers=auth(datos[quien])).status_code == 403


@pytest.mark.parametrize("ruta", [INSCRIPCIONES, AVISOS])
def test_estudiante_sin_perfil_recibe_403(client, session, ruta):
    sin_perfil, = _guardar(session, Usuario(dni="80000010", password_hash="x", rol=Rol.estudiante))
    assert client.get(ruta, headers=auth(sin_perfil)).status_code == 403


@pytest.mark.parametrize("ruta", [INSCRIPCIONES, AVISOS])
def test_sin_token_responde_401(client, ruta):
    assert client.get(ruta).status_code == 401
