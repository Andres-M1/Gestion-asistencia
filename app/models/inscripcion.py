from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models.alumno import Alumno
    from app.models.catedra import Catedra


class Inscripcion(SQLModel, table=True):
    # Un alumno no puede inscribirse dos veces en la misma cátedra
    __table_args__ = (UniqueConstraint("alumno_id", "catedra_id", name="uq_inscripcion_alumno_catedra"),)

    id: int | None = Field(default=None, primary_key=True)
    alumno_id: int = Field(foreign_key="alumno.id")
    catedra_id: int = Field(foreign_key="catedra.id")

    alumno: "Alumno" = Relationship(back_populates="inscripciones")
    catedra: "Catedra" = Relationship(back_populates="inscripciones")
