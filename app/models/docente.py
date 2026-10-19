from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.catedra import Catedra


class Docente(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    dni: str = Field(unique=True)
    nombre: str
    apellido: str
    email: str = Field(unique=True)

    catedras: list["Catedra"] = Relationship(back_populates="docente")
