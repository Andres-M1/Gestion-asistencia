from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.catedra import Catedra


class Materia(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    carrera_id: int = Field(foreign_key="carrera.id")
    nombre: str

    carrera: "Carrera" = Relationship(back_populates="materias")
    catedras: list["Catedra"] = Relationship(back_populates="materia")
