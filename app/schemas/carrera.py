"""Esquemas de entrada/salida de la API para Carrera."""
from sqlmodel import SQLModel


class CarreraCreate(SQLModel):
    nombre: str


class CarreraUpdate(SQLModel):
    nombre: str | None = None


class CarreraRead(SQLModel):
    id: int
    nombre: str
