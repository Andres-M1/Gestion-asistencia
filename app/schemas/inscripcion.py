"""Esquemas de entrada/salida de la API para Inscripción."""
from sqlmodel import SQLModel


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
