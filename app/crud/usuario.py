"""Acceso a datos de Usuario."""
from sqlmodel import Session, select

from app.core.security import hash_password
from app.models.usuario import Rol, Usuario


def obtener(session: Session, usuario_id: int) -> Usuario | None:
    return session.get(Usuario, usuario_id)


def obtener_por_dni(session: Session, dni: str) -> Usuario | None:
    return session.exec(select(Usuario).where(Usuario.dni == dni)).first()


def crear(session: Session, dni: str, password: str, rol: Rol) -> Usuario:
    usuario = Usuario(dni=dni, password_hash=hash_password(password), rol=rol)
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario
