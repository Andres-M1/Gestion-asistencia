"""Esquemas de entrada/salida de la API para avisos de ausencia (HU-02, HU-03)."""
from datetime import date, datetime, time

from sqlmodel import SQLModel


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


class DocenteResumen(SQLModel):
    nombre: str
    apellido: str


class AvisoDetalle(SQLModel):
    """Un aviso con los datos de su clase. Lo usan HU-02, HU-03, HU-05 y HU-09.

    No incluye estado: un aviso registrado siempre está "activo" (HU-04 descartada).
    """

    id: int
    fecha: date
    materia: str
    comision: str
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    docente: DocenteResumen
    creado_en: datetime
