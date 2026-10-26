from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.catedra import Catedra
    from app.models.usuario import Usuario


class Docente(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", unique=True)
    nombre: str
    apellido: str
    email: str = Field(unique=True)

    usuario: "Usuario" = Relationship(back_populates="docente")
    catedras: list["Catedra"] = Relationship(back_populates="docente")
