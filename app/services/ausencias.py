"""Reglas de negocio de los avisos de ausencia (HU-02).

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

from sqlmodel import Session, select

from app.crud import base as crud
from app.models.ausencia import Ausencia
from app.models.catedra import Catedra
from app.models.docente import Docente
from app.schemas.ausencia import ClaseDisponible

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
ANTICIPACION_MINIMA = timedelta(hours=1)
VENTANA = timedelta(days=7)


class CatedraNoEncontrada(Exception):
    """La cátedra no existe o no es del docente."""


class AvisoInvalido(Exception):
    """La clase elegida no cumple las reglas para registrar un aviso."""


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
