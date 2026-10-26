"""Aviso de que el docente de una cátedra no dará clase en una fecha (HU-02)."""
from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import DateTime, Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models.catedra import Catedra


class EstadoAusencia(str, Enum):
    activo = "activo"


class Ausencia(SQLModel, table=True):
    # Una cátedra no puede tener dos avisos cargados el mismo día
    __table_args__ = (UniqueConstraint("catedra_id", "fecha", name="uq_ausencia_catedra_fecha"),)

    id: int | None = Field(default=None, primary_key=True)
    catedra_id: int = Field(foreign_key="catedra.id")
    fecha: date
    estado: EstadoAusencia = EstadoAusencia.activo
    creado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )

    catedra: "Catedra" = Relationship(back_populates="ausencias")
