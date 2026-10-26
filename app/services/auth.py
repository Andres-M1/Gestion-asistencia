"""Lógica de autenticación (HU-01)."""
from sqlmodel import Session

from app.core.security import hash_password, verify_password
from app.crud import usuario as crud_usuario
from app.models.usuario import Usuario

# Hash ficticio: si el DNI no existe igual se verifica una contraseña,
# así la respuesta tarda lo mismo y no revela qué DNIs están registrados.
_HASH_FICTICIO = hash_password("contraseña-ficticia")


def autenticar(session: Session, dni: str, password: str) -> Usuario | None:
    usuario = crud_usuario.obtener_por_dni(session, dni)
    if usuario is None:
        verify_password(password, _HASH_FICTICIO)
        return None
    if not verify_password(password, usuario.password_hash) or not usuario.activo:
        return None
    return usuario
