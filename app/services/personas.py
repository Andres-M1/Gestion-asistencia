"""Alta y edición de docentes y alumnos junto con su Usuario (HU-08).

Usuario y perfil se guardan en una sola transacción: o se crean los dos, o ninguno.
"""
from typing import TypeVar

from sqlmodel import Session

from app.core.security import hash_password
from app.models.alumno import Alumno
from app.models.docente import Docente
from app.models.usuario import Rol, Usuario
from app.schemas.persona import PersonaCreate, PersonaUpdate

Perfil = TypeVar("Perfil", Docente, Alumno)

_CAMPOS_USUARIO = {"dni", "password", "activo"}


def crear(session: Session, modelo: type[Perfil], rol: Rol, data: PersonaCreate) -> Perfil:
    usuario = Usuario(dni=data.dni, password_hash=hash_password(data.password), rol=rol)
    perfil = modelo(**data.model_dump(exclude=_CAMPOS_USUARIO), usuario=usuario)
    session.add(perfil)
    session.commit()
    session.refresh(perfil)
    return perfil


def actualizar(session: Session, perfil: Perfil, data: PersonaUpdate) -> Perfil:
    cambios = data.model_dump(exclude_unset=True)
    if "password" in cambios:
        perfil.usuario.password_hash = hash_password(cambios.pop("password"))
    if "activo" in cambios:
        perfil.usuario.activo = cambios.pop("activo")
    perfil.sqlmodel_update(cambios)
    session.add(perfil)
    session.commit()
    session.refresh(perfil)
    return perfil


def a_dict(perfil: Perfil) -> dict:
    """Une los datos del perfil con los del usuario para la respuesta de la API."""
    return {**perfil.model_dump(), "dni": perfil.usuario.dni, "activo": perfil.usuario.activo}
