"""Endpoints de Materia: /api/v1/materias (solo administrador)."""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.api.errores import manejar_integridad, obtener_o_404
from app.crud import base as crud
from app.models.materia import Materia
from app.models.usuario import Rol
from app.schemas.materia import MateriaCreate, MateriaRead, MateriaUpdate

router = APIRouter(prefix="/materias", dependencies=[Depends(requiere_rol(Rol.admin))])


def _obtener(session: SessionDep, materia_id: int) -> Materia:
    return obtener_o_404(crud.obtener(session, Materia, materia_id), "Materia no encontrada")


@router.post("/", response_model=MateriaRead, status_code=status.HTTP_201_CREATED)
def crear(data: MateriaCreate, session: SessionDep):
    with manejar_integridad(session):
        return crud.crear(session, Materia.model_validate(data))


@router.get("/", response_model=list[MateriaRead])
def listar(
    session: SessionDep,
    carrera_id: int | None = None,
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    filtros = [Materia.carrera_id == carrera_id] if carrera_id is not None else []
    return crud.listar(session, Materia, *filtros, offset=offset, limit=limit)


@router.get("/{materia_id}", response_model=MateriaRead)
def obtener(materia_id: int, session: SessionDep):
    return _obtener(session, materia_id)


@router.patch("/{materia_id}", response_model=MateriaRead)
def actualizar(materia_id: int, data: MateriaUpdate, session: SessionDep):
    materia = _obtener(session, materia_id)
    with manejar_integridad(session):
        return crud.actualizar(session, materia, data.model_dump(exclude_unset=True))


@router.delete("/{materia_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(materia_id: int, session: SessionDep):
    materia = _obtener(session, materia_id)
    with manejar_integridad(session, al_borrar=True):
        crud.borrar(session, materia)
