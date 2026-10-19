from datetime import time
from typing import TYPE_CHECKING

from sqlmodel import CheckConstraint, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.ausencia import Ausencia
    from app.models.docente import Docente
    from app.models.inscripcion import Inscripcion
    from app.models.materia import Materia


class Catedra(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="ck_catedra_dia_semana"),  # 1 = lunes ... 7 = domingo
        CheckConstraint("hora_fin > hora_inicio", name="ck_catedra_horario"),
    )

    id: int | None = Field(default=None, primary_key=True)
    materia_id: int = Field(foreign_key="materia.id")
    docente_id: int = Field(foreign_key="docente.id")
    dia_semana: int
    hora_inicio: time
    hora_fin: time

    materia: "Materia" = Relationship(back_populates="catedras")
    docente: "Docente" = Relationship(back_populates="catedras")
    inscripciones: list["Inscripcion"] = Relationship(back_populates="catedra")
    ausencias: list["Ausencia"] = Relationship(back_populates="catedra")
