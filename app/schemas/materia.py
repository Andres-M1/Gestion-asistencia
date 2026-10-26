"""Esquemas de entrada/salida de la API para Materia."""
from sqlmodel import Field, SQLModel


class MateriaCreate(SQLModel):
    carrera_id: int
    nombre: str = Field(min_length=1)


class MateriaUpdate(SQLModel):
    carrera_id: int | None = None
    nombre: str | None = Field(default=None, min_length=1)


class MateriaRead(SQLModel):
    id: int
    carrera_id: int
    nombre: str
