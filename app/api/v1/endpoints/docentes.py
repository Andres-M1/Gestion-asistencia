"""Endpoints de Docente: /api/v1/docentes (solo administrador, HU-08).

No hay DELETE: para que un docente no pueda entrar más se lo desactiva con
PATCH {"activo": false}. Así se conserva el historial de sus avisos.
"""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.api.errores import manejar_integridad, obtener_o_404
from app.crud import base as crud
from app.models.docente import Docente
from app.models.usuario import Rol
from app.schemas.persona import DocenteCreate, DocenteRead, DocenteUpdate
from app.services import personas

router = APIRouter(prefix="/docentes", dependencies=[Depends(requiere_rol(Rol.admin))])


def _obtener(session: SessionDep, docente_id: int) -> Docente:
    return obtener_o_404(crud.obtener(session, Docente, docente_id), "Docente no encontrado")


@router.post("/", response_model=DocenteRead, status_code=status.HTTP_201_CREATED)
def crear(data: DocenteCreate, session: SessionDep):
    with manejar_integridad(session):
        return personas.a_dict(personas.crear(session, Docente, Rol.docente, data))


@router.get("/", response_model=list[DocenteRead])
def listar(session: SessionDep, offset: int = 0, limit: int = Query(default=100, le=100)):
    return [personas.a_dict(d) for d in crud.listar(session, Docente, offset=offset, limit=limit)]


@router.get("/{docente_id}", response_model=DocenteRead)
def obtener(docente_id: int, session: SessionDep):
    return personas.a_dict(_obtener(session, docente_id))


@router.patch("/{docente_id}", response_model=DocenteRead)
def actualizar(docente_id: int, data: DocenteUpdate, session: SessionDep):
    docente = _obtener(session, docente_id)
    with manejar_integridad(session):
        return personas.a_dict(personas.actualizar(session, docente, data))
