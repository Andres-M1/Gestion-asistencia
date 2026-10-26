"""Esquemas de entrada/salida de la API para login y usuario actual."""
from sqlmodel import SQLModel

from app.models.usuario import Rol


class LoginRequest(SQLModel):
    dni: str
    password: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class PerfilRead(SQLModel):
    id: int
    nombre: str
    apellido: str
    email: str


class UsuarioMe(SQLModel):
    id: int
    dni: str
    rol: Rol
    perfil: PerfilRead | None = None  # datos de Docente o Alumno; None para el admin
