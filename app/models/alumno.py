from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.inscripcion import Inscripcion


class Alumno(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    carrera_id: int = Field(foreign_key="carrera.id")
    dni: str = Field(unique=True)
    nombre: str
    apellido: str
    email: str = Field(unique=True)

    carrera: "Carrera" = Relationship(back_populates="alumnos")
    inscripciones: list["Inscripcion"] = Relationship(back_populates="alumno")
