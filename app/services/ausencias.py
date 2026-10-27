"""Reglas de negocio de los avisos de ausencia (HU-02, HU-03, HU-05).

Una clase = una cátedra en una fecha concreta. El docente puede avisar sobre una clase si:
  - la cátedra es suya;
  - la fecha cae en el día de cursada de la cátedra;
  - faltan al menos ANTICIPACION_MINIMA para su hora de inicio;
  - empieza dentro de VENTANA desde ahora;
  - no tiene ya un aviso.
Todo se compara en hora de Argentina, nunca con la hora del servidor (UTC).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.crud import base as crud
from app.models.ausencia import Ausencia
from app.models.catedra import Catedra
from app.models.alumno import Alumno
from app.models.docente import Docente
from app.models.inscripcion import Inscripcion
from app.schemas.ausencia import AvisoDetalle, ClaseDisponible, DocenteResumen

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
ANTICIPACION_MINIMA = timedelta(hours=1)
VENTANA = timedelta(days=7)


class CatedraNoEncontrada(Exception):
    """La cátedra no existe o no es del docente."""


class AvisoInvalido(Exception):
    """La clase elegida no cumple las reglas para registrar un aviso."""


class SinInscripcionVigente(Exception):
    """El alumno no tiene una inscripción vigente en la cátedra pedida."""


def ahora() -> datetime:
    """Momento actual en Argentina. Los tests la reemplazan para fijar la hora."""
    return datetime.now(ZONA)


def _ahora_argentina() -> datetime:
    return ahora().astimezone(ZONA)


def _inicio(catedra: Catedra, fecha: date) -> datetime:
    return datetime.combine(fecha, catedra.hora_inicio, tzinfo=ZONA)


def clases_disponibles(session: Session, docente: Docente) -> list[ClaseDisponible]:
    momento = _ahora_argentina()
    desde, hasta = momento + ANTICIPACION_MINIMA, momento + VENTANA
    catedras = docente.catedras
    if not catedras:
        return []

    con_aviso = set(
        session.exec(
            select(Ausencia.catedra_id, Ausencia.fecha).where(
                Ausencia.catedra_id.in_([c.id for c in catedras]),
                Ausencia.fecha.between(desde.date(), hasta.date()),
            )
        )
    )

    clases = []
    dia = desde.date()
    while dia <= hasta.date():
        for catedra in catedras:
            if catedra.dia_semana != dia.isoweekday() or (catedra.id, dia) in con_aviso:
                continue
            if desde <= _inicio(catedra, dia) <= hasta:
                clases.append(
                    ClaseDisponible(
                        catedra_id=catedra.id,
                        fecha=dia,
                        materia=catedra.materia.nombre,
                        comision=catedra.comision,
                        dia_semana=catedra.dia_semana,
                        hora_inicio=catedra.hora_inicio,
                        hora_fin=catedra.hora_fin,
                    )
                )
        dia += timedelta(days=1)
    return sorted(clases, key=lambda c: (c.fecha, c.hora_inicio))


def registrar_aviso(session: Session, docente: Docente, catedra_id: int, fecha: date) -> Ausencia:
    """Vuelve a validar todas las reglas: no confía en que el cliente mandó una opción de la lista.

    Si ya existe un aviso para esa cátedra y fecha, el commit lanza IntegrityError
    (uq_ausencia_catedra_fecha) y el endpoint lo convierte en 409.
    """
    catedra = crud.obtener(session, Catedra, catedra_id)
    if catedra is None or catedra.docente_id != docente.id:
        raise CatedraNoEncontrada

    if fecha.isoweekday() != catedra.dia_semana:
        raise AvisoInvalido("La fecha no corresponde al día de cursada de la cátedra")

    momento = _ahora_argentina()
    inicio = _inicio(catedra, fecha)
    if inicio < momento + ANTICIPACION_MINIMA:
        raise AvisoInvalido("Solo se puede avisar hasta 1 hora antes del inicio de la clase")
    if inicio > momento + VENTANA:
        raise AvisoInvalido("Solo se puede avisar sobre clases de los próximos 7 días")

    return crud.crear(session, Ausencia(catedra_id=catedra.id, fecha=fecha))


def a_detalle(aviso: Ausencia) -> AvisoDetalle:
    """Arma la respuesta de un aviso con los datos de su clase."""
    catedra = aviso.catedra
    return AvisoDetalle(
        id=aviso.id,
        fecha=aviso.fecha,
        materia=catedra.materia.nombre,
        comision=catedra.comision,
        dia_semana=catedra.dia_semana,
        hora_inicio=catedra.hora_inicio,
        hora_fin=catedra.hora_fin,
        docente=DocenteResumen(nombre=catedra.docente.nombre, apellido=catedra.docente.apellido),
        creado_en=aviso.creado_en,
    )


def _con_detalle(consulta):
    """Carga cátedra, materia y docente de cada aviso en 3 consultas en total, no una por aviso."""
    return consulta.options(
        selectinload(Ausencia.catedra).options(selectinload(Catedra.materia), selectinload(Catedra.docente))
    )


def avisos_del_docente(session: Session, docente: Docente, offset: int = 0, limit: int = 100) -> list[AvisoDetalle]:
    """Historial de avisos del docente (HU-03), pasados y futuros, del más nuevo al más viejo.

    El desempate por hora de inicio e id hace que el orden sea siempre el mismo,
    así la paginación no repite ni saltea avisos.
    """
    consulta = (
        select(Ausencia)
        .join(Catedra)
        .where(Catedra.docente_id == docente.id)
        .order_by(Ausencia.fecha.desc(), Catedra.hora_inicio.desc(), Ausencia.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [a_detalle(aviso) for aviso in session.exec(_con_detalle(consulta))]


def avisos_del_alumno(
    session: Session, alumno: Alumno, catedra_id: int | None = None, offset: int = 0, limit: int = 100
) -> list[AvisoDetalle]:
    """Avisos de hoy en adelante (hora de Argentina) de las cátedras donde el alumno
    tiene inscripción vigente (HU-05), del más próximo al más lejano.

    Con catedra_id, solo los de esa cátedra; si el alumno no tiene inscripción
    vigente en ella, lanza SinInscripcionVigente.
    """
    vigentes = select(Inscripcion.catedra_id).where(
        Inscripcion.alumno_id == alumno.id, Inscripcion.vigente == True  # noqa: E712
    )
    if catedra_id is not None:
        if session.exec(vigentes.where(Inscripcion.catedra_id == catedra_id)).first() is None:
            raise SinInscripcionVigente
        de_sus_catedras = Ausencia.catedra_id == catedra_id
    else:
        de_sus_catedras = Ausencia.catedra_id.in_(vigentes)

    consulta = (
        select(Ausencia)
        .join(Catedra)
        .where(de_sus_catedras, Ausencia.fecha >= _ahora_argentina().date())
        .order_by(Ausencia.fecha, Catedra.hora_inicio, Ausencia.id)
        .offset(offset)
        .limit(limit)
    )
    return [a_detalle(aviso) for aviso in session.exec(_con_detalle(consulta))]
