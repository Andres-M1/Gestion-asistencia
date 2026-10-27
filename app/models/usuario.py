"""Credenciales y rol de cada persona que se loguea (HU-01, HU-08)."""
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.alumno import Alumno
    from app.models.docente import Docente


class Rol(str, Enum):
    admin = "admin"
    docente = "docente"
    estudiante = "estudiante"


class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    dni: str = Field(unique=True, index=True)
    password_hash: str
    rol: Rol
    activo: bool = True
    email: str | None = None  # para notificar al preceptor (admin); docentes y alumnos usan el de su perfil
    fcm_token: str | None = None  # token de Firebase del celular (un dispositivo por usuario)

    # Relación 1 a 1: un usuario tiene como mucho un perfil (el admin no tiene ninguno)
    docente: Optional["Docente"] = Relationship(back_populates="usuario", sa_relationship_kwargs={"uselist": False})
    alumno: Optional["Alumno"] = Relationship(back_populates="usuario", sa_relationship_kwargs={"uselist": False})
