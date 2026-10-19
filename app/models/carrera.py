from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.alumno import Alumno
    from app.models.materia import Materia


class Carrera(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)

    materias: list["Materia"] = Relationship(back_populates="carrera")
    alumnos: list["Alumno"] = Relationship(back_populates="carrera")
