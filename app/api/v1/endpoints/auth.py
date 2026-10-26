"""Endpoints de autenticación: /api/v1/auth (HU-01)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, PerfilRead, Token, UsuarioMe
from app.services.auth import autenticar

router = APIRouter(prefix="/auth")


def _login(session: SessionDep, dni: str, password: str) -> Token:
    usuario = autenticar(session, dni, password)
    if usuario is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "DNI o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(usuario.id, usuario.rol.value))


@router.post("/login", response_model=Token)
def login(data: LoginRequest, session: SessionDep):
    """Login para el frontend: recibe JSON {dni, password}."""
    return _login(session, data.dni, data.password)


@router.post("/token", response_model=Token, include_in_schema=False)
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    """Login en formato OAuth2 (username = DNI) para el botón 'Authorize' de /docs."""
    return _login(session, form.username, form.password)


@router.get("/me", response_model=UsuarioMe)
def me(usuario: CurrentUser):
    """Datos del usuario logueado, con su perfil de docente o alumno."""
    perfil = usuario.docente or usuario.alumno
    return UsuarioMe(
        id=usuario.id,
        dni=usuario.dni,
        rol=usuario.rol,
        perfil=PerfilRead.model_validate(perfil, from_attributes=True) if perfil else None,
    )
