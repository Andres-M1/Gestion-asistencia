"""Esquemas de entrada/salida de la API para avisos de ausencia (HU-02)."""
from datetime import date, datetime, time

from sqlmodel import SQLModel

from app.models.ausencia import EstadoAusencia


class ClaseDisponible(SQLModel):
    """Una clase concreta (cátedra + fecha) sobre la que el docente puede avisar."""

    catedra_id: int
    fecha: date
    materia: str
    comision: str
    dia_semana: int
    hora_inicio: time
    hora_fin: time


class AvisoCreate(SQLModel):
    catedra_id: int
    fecha: date


class AvisoRead(SQLModel):
    id: int
    catedra_id: int
    fecha: date
    estado: EstadoAusencia
    creado_en: datetime
