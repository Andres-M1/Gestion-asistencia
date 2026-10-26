"""Esquemas para dar de alta y editar docentes y alumnos (HU-08).

Cada alta crea dos filas: el Usuario (DNI, contraseña, rol) y el perfil (Docente o Alumno).
"""
from typing import Annotated

from pydantic import EmailStr, StringConstraints
from sqlmodel import Field, SQLModel

# Solo números, sin puntos (ej. 12345678)
Dni = Annotated[str, StringConstraints(pattern=r"^\d{6,10}$")]


class PersonaCreate(SQLModel):
    dni: Dni
    password: str = Field(min_length=8)
    nombre: str = Field(min_length=1)
    apellido: str = Field(min_length=1)
    email: EmailStr


class PersonaUpdate(SQLModel):
    nombre: str | None = Field(default=None, min_length=1)
    apellido: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, description="Asigna una contraseña nueva")
    activo: bool | None = Field(default=None, description="false = no puede loguearse")


class PersonaRead(SQLModel):
    id: int
    dni: str
    nombre: str
    apellido: str
    email: str
    activo: bool


class DocenteCreate(PersonaCreate):
    pass


class DocenteUpdate(PersonaUpdate):
    pass


class DocenteRead(PersonaRead):
    pass


class AlumnoCreate(PersonaCreate):
    carrera_id: int


class AlumnoUpdate(PersonaUpdate):
    carrera_id: int | None = None


class AlumnoRead(PersonaRead):
    carrera_id: int
