"""HU-06: al registrarse un aviso se notifica por correo y push. Token FCM de cada usuario.

SMTP y FCM son falsos (fixture `envios` de conftest): nunca hay envíos reales.
Hora fijada: lunes 02/11/2026 10:00. El aviso de prueba es de "Programación II" 1K1,
martes 03/11/2026 18:00-20:00, docente A ("Doc 80000001").
"""
import logging
from contextlib import nullcontext
from datetime import datetime
from unittest import mock

import pytest
from firebase_admin import exceptions, messaging

from app.core import push
from app.core.config import settings
from app.crud.usuario import obtener_por_dni
from app.models import Alumno, Inscripcion, Usuario
from app.models.usuario import Rol
from app.scripts import crear_admin
from app.services import ausencias, notificaciones
from tests.conftest import auth

AR = ausencias.ZONA
FCM = "/api/v1/auth/me/fcm-token"


@pytest.fixture(autouse=True)
def lunes_10hs(fijar_ahora):
    fijar_ahora(datetime(2026, 11, 2, 10, 0, tzinfo=AR))


def _guardar(session, *objetos):
    session.add_all(objetos)
    session.commit()
    return objetos


@pytest.fixture
def esc(session, datos):
    """Destinatarios posibles de un aviso en martes_a (Programación II 1K1)."""
    catedra = datos["martes_a"]
    carrera_id = datos["u_alumno"].alumno.carrera_id
    contador = iter(range(100))

    def alumno(nombre, catedra_inscripta, vigente=True, activo=True, token=None):
        n = next(contador)
        usuario, = _guardar(session, Usuario(dni=f"7000000{n}", password_hash="x", rol=Rol.estudiante,
                                             activo=activo, fcm_token=token))
        alu, = _guardar(session, Alumno(usuario_id=usuario.id, carrera_id=carrera_id, nombre=nombre,
                                        apellido="Test", email=f"{nombre}@gestion-test.com.ar"))
        if catedra_inscripta is not None:
            _guardar(session, Inscripcion(alumno_id=alu.id, catedra_id=catedra_inscripta.id, vigente=vigente))
        return usuario

    def admin(nombre, email, activo=True):
        n = next(contador)
        return _guardar(session, Usuario(dni=f"6000000{n}", password_hash="x", rol=Rol.admin,
                                         activo=activo, email=email))[0]

    return {
        "catedra": catedra,
        "vigente_con_token": alumno("vigente1", catedra, token="tok-vigente1"),
        "vigente_sin_token": alumno("vigente2", catedra),
        "vigente_inactivo": alumno("inactivo", catedra, activo=False, token="tok-inactivo"),
        "no_vigente": alumno("novigente", catedra, vigente=False, token="tok-novigente"),
        "otra_catedra": alumno("otracatedra", datos["martes_b"], token="tok-otracatedra"),
        "admin_con_email": admin("preceptor", "preceptor@gestion-test.com.ar"),
        "admin_sin_email": admin("sinemail", None),
        "admin_inactivo": admin("inactivo", "admin.inactivo@gestion-test.com.ar", activo=False),
    }


def avisar(client, datos, catedra=None):
    catedra = catedra or datos["martes_a"]
    r = client.post("/api/v1/docente/avisos", headers=auth(datos["u_doc_a"]),
                    json={"catedra_id": catedra.id, "fecha": "2026-11-03"})
    assert r.status_code == 201, r.text
    return r.json()


def correos_a(envios):
    return sorted(m["To"] for m in envios.correos)


# --- Destinatarios -------------------------------------------------------------------

def test_correo_a_alumnos_vigentes_activos_y_preceptores_activos_con_email(client, datos, esc, envios):
    avisar(client, datos)
    assert correos_a(envios) == [
        "preceptor@gestion-test.com.ar", "vigente1@gestion-test.com.ar", "vigente2@gestion-test.com.ar",
    ]


def test_un_correo_por_destinatario(client, datos, esc, envios):
    avisar(client, datos)
    assert all("," not in m["To"] and m["Cc"] is None and m["Bcc"] is None for m in envios.correos)
    assert len(envios.correos) == len(set(correos_a(envios)))


def test_push_solo_a_alumnos_vigentes_activos_con_token(client, datos, esc, envios):
    avisar(client, datos)
    assert envios.tandas_push == [["tok-vigente1"]]


def test_no_notifica_a_no_vigentes_ni_a_otros_alumnos_ni_a_inactivos(client, datos, esc, envios):
    avisar(client, datos)
    excluidos = {"novigente", "otracatedra", "inactivo", "admin.inactivo"}
    assert not any(m["To"].split("@")[0] in excluidos for m in envios.correos)
    assert not {"tok-novigente", "tok-otracatedra", "tok-inactivo"} & set(sum(envios.tandas_push, []))


def test_sin_destinatarios_no_envia_nada(client, datos, envios):
    # Sin el escenario `esc`: nadie inscripto en martes_a y el admin de conftest no tiene email
    avisar(client, datos)
    assert envios.correos == []
    assert envios.tandas_push == []


# --- Contenido ---------------------------------------------------------------------

def test_contenido_del_correo_y_del_push(client, datos, esc, envios, monkeypatch):
    titulos = []
    original = push.enviar
    monkeypatch.setattr(push, "enviar", lambda t, titulo, cuerpo: titulos.append((titulo, cuerpo)) or original(t, titulo, cuerpo))
    avisar(client, datos)
    mensaje = envios.correos[0]
    assert mensaje["Subject"] == "Aviso de ausencia: Programación II 1K1 - martes 03/11/2026"
    assert mensaje["From"] == "avisos@gestion-test.com.ar"
    texto = mensaje.get_content()
    for dato in ("Doc 80000001", "Programación II", "1K1", "martes 03/11/2026", "18:00 a 20:00"):
        assert dato in texto
    assert titulos == [("Clase suspendida: Programación II 1K1", "martes 03/11/2026, 18:00 a 20:00. Docente: Doc 80000001")]


# --- Fallos de envío ---------------------------------------------------------------

def test_si_falla_un_correo_se_envian_los_demas_y_el_aviso_se_crea(client, datos, esc, envios):
    envios.fallar_correo_a = {"vigente1@gestion-test.com.ar"}
    aviso = avisar(client, datos)
    assert correos_a(envios) == ["preceptor@gestion-test.com.ar", "vigente2@gestion-test.com.ar"]
    assert envios.tandas_push == [["tok-vigente1"]]
    assert aviso["id"]


def test_si_falla_la_conexion_smtp_igual_se_crea_el_aviso_y_se_envia_el_push(client, datos, esc, envios, session):
    envios.error_conexion_smtp = ConnectionRefusedError("SMTP caído")
    aviso = avisar(client, datos)
    assert envios.correos == []
    assert envios.tandas_push == [["tok-vigente1"]]
    assert session.get(ausencias.Ausencia, aviso["id"]) is not None


def test_si_falla_fcm_igual_se_crea_el_aviso(client, datos, esc, envios, session):
    envios.error_fcm = exceptions.UnavailableError("FCM no disponible")
    aviso = avisar(client, datos)
    assert len(envios.correos) == 3
    assert session.get(ausencias.Ausencia, aviso["id"]) is not None


def test_si_falla_armar_los_destinatarios_igual_se_crea_el_aviso(client, datos, esc, envios, monkeypatch, session):
    monkeypatch.setattr(notificaciones, "_destinatarios", mock.Mock(side_effect=RuntimeError("falla simulada")))
    aviso = avisar(client, datos)
    assert envios.correos == []
    assert session.get(ausencias.Ausencia, aviso["id"]) is not None


# --- Tokens inválidos --------------------------------------------------------------

def test_tokens_unregistered_o_sender_id_mismatch_quedan_en_none(client, datos, esc, envios, session):
    usuarios = {}
    for token, nombre in [("tok-unreg", "a"), ("tok-sender", "b"), ("tok-invarg", "c"), ("tok-caido", "d")]:
        u = esc["vigente_sin_token"] if nombre == "a" else _alumno_vigente_extra(session, datos, esc, nombre)
        u.fcm_token = token
        _guardar(session, u)
        usuarios[token] = u
    envios.error_por_token = {
        "tok-unreg": messaging.UnregisteredError("token no registrado"),
        "tok-sender": messaging.SenderIdMismatchError("otro proyecto"),
        "tok-invarg": exceptions.InvalidArgumentError("mensaje mal armado"),
        "tok-caido": exceptions.UnavailableError("FCM no disponible"),
    }
    avisar(client, datos)
    for u in usuarios.values():
        session.refresh(u)
    assert usuarios["tok-unreg"].fcm_token is None
    assert usuarios["tok-sender"].fcm_token is None
    assert usuarios["tok-invarg"].fcm_token == "tok-invarg"  # solo se registra en el log
    assert usuarios["tok-caido"].fcm_token == "tok-caido"
    session.refresh(esc["vigente_con_token"])
    assert esc["vigente_con_token"].fcm_token == "tok-vigente1"


def _alumno_vigente_extra(session, datos, esc, nombre):
    usuario, = _guardar(session, Usuario(dni=f"7100000{ord(nombre)}", password_hash="x", rol=Rol.estudiante))
    alu, = _guardar(session, Alumno(usuario_id=usuario.id, carrera_id=datos["u_alumno"].alumno.carrera_id,
                                    nombre=nombre, apellido="Extra", email=f"extra.{nombre}@gestion-test.com.ar"))
    _guardar(session, Inscripcion(alumno_id=alu.id, catedra_id=esc["catedra"].id))
    return usuario


def test_push_en_tandas_de_500(envios):
    tokens = [f"tok-{i}" for i in range(1201)]
    assert push.enviar(tokens, "t", "c") == []
    assert [len(t) for t in envios.tandas_push] == [500, 500, 201]
    assert sum(envios.tandas_push, []) == tokens


# --- Sin credenciales --------------------------------------------------------------

def test_sin_credenciales_no_falla_y_saltea_los_envios(client, datos, esc, envios, monkeypatch, caplog):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS", None)
    with caplog.at_level(logging.WARNING):
        avisar(client, datos)
    assert envios.correos == []
    assert envios.tandas_push == []
    assert "SMTP no configurado" in caplog.text
    assert "Firebase no configurado" in caplog.text


def test_al_arrancar_advierte_si_falta_configuracion(monkeypatch, caplog):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS", None)
    with caplog.at_level(logging.WARNING):
        notificaciones.advertir_si_falta_configuracion()
    assert "SMTP no configurado" in caplog.text
    assert "FIREBASE_CREDENTIALS no configurado" in caplog.text


def test_credenciales_de_firebase_inexistentes_no_rompen(client, datos, esc, envios, monkeypatch, caplog):
    def falla():
        raise FileNotFoundError("secrets/no-existe.json")
    monkeypatch.setattr(push, "_obtener_app", falla)
    with caplog.at_level(logging.ERROR):
        avisar(client, datos)
    assert envios.tandas_push == []
    assert len(envios.correos) == 3
    assert "No se pudo iniciar Firebase" in caplog.text


# --- PUT / DELETE /auth/me/fcm-token -----------------------------------------------

@pytest.mark.parametrize("quien", ["u_alumno", "u_doc_a"])
def test_put_guarda_el_token_de_alumno_o_docente(client, datos, session, quien):
    assert client.put(FCM, headers=auth(datos[quien]), json={"token": "nuevo-token"}).status_code == 204
    session.refresh(datos[quien])
    assert datos[quien].fcm_token == "nuevo-token"


def test_put_le_quita_el_token_a_otro_usuario_del_mismo_celular(client, datos, session):
    client.put(FCM, headers=auth(datos["u_alumno"]), json={"token": "celular-1"})
    client.put(FCM, headers=auth(datos["u_doc_a"]), json={"token": "celular-1"})
    session.refresh(datos["u_alumno"])
    session.refresh(datos["u_doc_a"])
    assert datos["u_alumno"].fcm_token is None
    assert datos["u_doc_a"].fcm_token == "celular-1"


def test_delete_borra_el_token(client, datos, session):
    client.put(FCM, headers=auth(datos["u_alumno"]), json={"token": "celular-1"})
    assert client.delete(FCM, headers=auth(datos["u_alumno"])).status_code == 204
    session.refresh(datos["u_alumno"])
    assert datos["u_alumno"].fcm_token is None


def test_put_con_token_vacio_da_422(client, datos):
    assert client.put(FCM, headers=auth(datos["u_alumno"]), json={"token": ""}).status_code == 422


@pytest.mark.parametrize("metodo", ["put", "delete"])
def test_admin_no_registra_celular(client, datos, metodo):
    r = getattr(client, metodo)(FCM, headers=auth(datos["u_admin"]), **({"json": {"token": "x"}} if metodo == "put" else {}))
    assert r.status_code == 403


@pytest.mark.parametrize("metodo", ["put", "delete"])
def test_fcm_token_sin_login_da_401(client, metodo):
    r = getattr(client, metodo)(FCM, **({"json": {"token": "x"}} if metodo == "put" else {}))
    assert r.status_code == 401


# --- crear_admin.py con email ------------------------------------------------------

def _correr_crear_admin(session, argv, entrada_email=""):
    with mock.patch.object(crear_admin, "Session", lambda _engine: nullcontext(session)), \
         mock.patch("sys.argv", ["crear_admin", *argv]), \
         mock.patch("getpass.getpass", return_value="clave-segura-1"), \
         mock.patch("builtins.input", return_value=entrada_email):
        crear_admin.main()


def test_crear_admin_con_email_por_argumento(session, capsys):
    _correr_crear_admin(session, ["--dni", "50000001", "--email", "pre@gestion-test.com.ar"])
    assert obtener_por_dni(session, "50000001").email == "pre@gestion-test.com.ar"


def test_crear_admin_pide_el_email_por_teclado(session):
    _correr_crear_admin(session, ["--dni", "50000002"], entrada_email="tecla@gestion-test.com.ar")
    assert obtener_por_dni(session, "50000002").email == "tecla@gestion-test.com.ar"


def test_crear_admin_sin_email(session):
    _correr_crear_admin(session, ["--dni", "50000003"], entrada_email="")
    assert obtener_por_dni(session, "50000003").email is None


def test_crear_admin_rechaza_email_invalido(session):
    with pytest.raises(SystemExit, match="Email inválido"):
        _correr_crear_admin(session, ["--dni", "50000004", "--email", "no-es-email"])
    assert obtener_por_dni(session, "50000004") is None
