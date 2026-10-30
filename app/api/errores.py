"""Traduce errores de la base de datos a respuestas HTTP con mensajes claros."""
from contextlib import contextmanager

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

# Nombre de la restricción (ver naming_convention en app/models/__init__.py) -> mensaje
MENSAJES = {
    "uq_carrera_nombre": "Ya existe una carrera con ese nombre",
    "ix_usuario_dni": "Ya existe un usuario con ese DNI",
    "uq_docente_email": "Ya existe un docente con ese email",
    "uq_alumno_email": "Ya existe un alumno con ese email",
    "uq_catedra_materia_comision": "Esa materia ya tiene una cátedra con esa comisión",
    "uq_inscripcion_alumno_catedra": "El alumno ya está inscripto en esa cátedra",
    "uq_ausencia_catedra_fecha": "Ya hay un aviso para esa cátedra en esa fecha",
    "ck_catedra_dia_semana": "dia_semana debe estar entre 1 (lunes) y 7 (domingo)",
    "ck_catedra_horario": "hora_fin debe ser posterior a hora_inicio",
    "fk_materia_carrera_id_carrera": "La carrera indicada no existe",
    "fk_alumno_carrera_id_carrera": "La carrera indicada no existe",
    "fk_catedra_materia_id_materia": "La materia indicada no existe",
    "fk_catedra_docente_id_docente": "El docente indicado no existe",
    "fk_inscripcion_alumno_id_alumno": "El alumno indicado no existe",
    "fk_inscripcion_catedra_id_catedra": "La cátedra indicada no existe",
    "fk_ausencia_catedra_id_catedra": "La cátedra indicada no existe",
    "fk_ausencia_docente_id_docente": "El docente indicado no existe",
}

_UNICO, _CLAVE_FORANEA = "23505", "23503"  # códigos de error de PostgreSQL


@contextmanager
def manejar_integridad(session: Session, al_borrar: bool = False):
    """Envuelve una operación que hace commit y convierte IntegrityError en HTTPException."""
    try:
        yield
    except IntegrityError as e:
        session.rollback()
        if al_borrar:
            raise HTTPException(status.HTTP_409_CONFLICT, "No se puede borrar: tiene registros asociados")
        codigo = getattr(e.orig, "sqlstate", None)
        restriccion = getattr(getattr(e.orig, "diag", None), "constraint_name", None)
        mensaje = MENSAJES.get(restriccion, "Los datos violan una restricción de la base")
        if codigo == _CLAVE_FORANEA:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, mensaje)
        if codigo == _UNICO:
            raise HTTPException(status.HTTP_409_CONFLICT, mensaje)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, mensaje)


def obtener_o_404(obj, mensaje: str):
    """Devuelve obj, o lanza 404 con el mensaje si es None."""
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, mensaje)
    return obj
