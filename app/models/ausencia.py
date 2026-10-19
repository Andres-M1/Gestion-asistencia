"""Aviso de que el docente de una cátedra no dará clase en una fecha."""
from datetime import date
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models.catedra import Catedra


class Ausencia(SQLModel, table=True):
    # Una cátedra no puede tener dos ausencias cargadas el mismo día
    __table_args__ = (UniqueConstraint("catedra_id", "fecha", name="uq_ausencia_catedra_fecha"),)

    id: int | None = Field(default=None, primary_key=True)
    catedra_id: int = Field(foreign_key="catedra.id")
    fecha: date
    motivo: str | None = None

    catedra: "Catedra" = Relationship(back_populates="ausencias")
