from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.inscripcion import Inscripcion
    from app.models.usuario import Usuario


class Alumno(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", unique=True)
    carrera_id: int = Field(foreign_key="carrera.id")
    nombre: str
    apellido: str
    email: str = Field(unique=True)

    usuario: "Usuario" = Relationship(back_populates="alumno")
    carrera: "Carrera" = Relationship(back_populates="alumnos")
    inscripciones: list["Inscripcion"] = Relationship(back_populates="alumno")
