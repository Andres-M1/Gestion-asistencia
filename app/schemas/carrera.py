"""Esquemas de entrada/salida de la API para Carrera."""
from sqlmodel import Field, SQLModel


class CarreraCreate(SQLModel):
    nombre: str = Field(min_length=1)


class CarreraUpdate(SQLModel):
    nombre: str | None = Field(default=None, min_length=1)


class CarreraRead(SQLModel):
    id: int
    nombre: str
