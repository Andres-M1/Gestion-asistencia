"""Esquemas de entrada/salida de la API para Cátedra (HU-10: asignar docente a materia)."""
from datetime import time

from pydantic import model_validator
from sqlmodel import Field, SQLModel

DIA_SEMANA = "1 = lunes ... 7 = domingo"


class CatedraCreate(SQLModel):
    materia_id: int
    docente_id: int
    comision: str = Field(min_length=1, description='Ej. "1K1"')
    dia_semana: int = Field(ge=1, le=7, description=DIA_SEMANA)
    hora_inicio: time
    hora_fin: time

    @model_validator(mode="after")
    def validar_horario(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return self


class CatedraUpdate(SQLModel):
    materia_id: int | None = None
    docente_id: int | None = None
    comision: str | None = Field(default=None, min_length=1)
    dia_semana: int | None = Field(default=None, ge=1, le=7, description=DIA_SEMANA)
    hora_inicio: time | None = None
    hora_fin: time | None = None


class CatedraRead(SQLModel):
    id: int
    materia_id: int
    docente_id: int
    comision: str
    dia_semana: int
    hora_inicio: time
    hora_fin: time
