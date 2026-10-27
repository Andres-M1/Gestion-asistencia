"""Inscripciones vistas por el alumno (HU-07)."""
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models.alumno import Alumno
from app.models.catedra import Catedra
from app.models.inscripcion import Inscripcion
from app.schemas.ausencia import DocenteResumen
from app.schemas.inscripcion import MiInscripcion


def inscripciones_vigentes(session: Session, alumno: Alumno) -> list[MiInscripcion]:
    """Todas las inscripciones vigentes del alumno (sin paginar: son pocas), en el orden de la semana."""
    consulta = (
        select(Inscripcion)
        .join(Catedra)
        .where(Inscripcion.alumno_id == alumno.id, Inscripcion.vigente == True)  # noqa: E712
        .options(selectinload(Inscripcion.catedra).options(selectinload(Catedra.materia), selectinload(Catedra.docente)))
        .order_by(Catedra.dia_semana, Catedra.hora_inicio, Catedra.id)
    )
    return [
        MiInscripcion(
            catedra_id=i.catedra.id,
            materia=i.catedra.materia.nombre,
            comision=i.catedra.comision,
            dia_semana=i.catedra.dia_semana,
            hora_inicio=i.catedra.hora_inicio,
            hora_fin=i.catedra.hora_fin,
            docente=DocenteResumen(nombre=i.catedra.docente.nombre, apellido=i.catedra.docente.apellido),
        )
        for i in session.exec(consulta)
    ]
