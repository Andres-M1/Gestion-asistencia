"""Esquemas de entrada/salida de la API para Inscripción."""
from datetime import time

from sqlmodel import SQLModel

from app.schemas.ausencia import DocenteResumen


class InscripcionCreate(SQLModel):
    alumno_id: int
    catedra_id: int


class InscripcionUpdate(SQLModel):
    vigente: bool


class InscripcionRead(SQLModel):
    id: int
    alumno_id: int
    catedra_id: int
    vigente: bool


class MiInscripcion(SQLModel):
    """Una inscripción vigente del alumno logueado, con los datos de su cátedra (HU-07)."""

    catedra_id: int
    materia: str
    comision: str
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    docente: DocenteResumen
