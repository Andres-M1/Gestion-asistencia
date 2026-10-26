"""Dependencias reutilizables para los endpoints."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import decode_access_token
from app.crud import usuario as crud_usuario
from app.models.usuario import Rol, Usuario

SessionDep = Annotated[Session, Depends(get_session)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(session: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]) -> Usuario:
    no_autorizado = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        usuario_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise no_autorizado
    usuario = crud_usuario.obtener(session, usuario_id)
    if usuario is None or not usuario.activo:
        raise no_autorizado
    return usuario


CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def requiere_rol(*roles: Rol):
    """Dependencia que deja pasar solo a usuarios con alguno de los roles indicados."""

    def verificar(usuario: CurrentUser) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tenés permiso para esta acción")
        return usuario

    return verificar


AdminUser = Annotated[Usuario, Depends(requiere_rol(Rol.admin))]
DocenteUser = Annotated[Usuario, Depends(requiere_rol(Rol.docente))]
EstudianteUser = Annotated[Usuario, Depends(requiere_rol(Rol.estudiante))]
