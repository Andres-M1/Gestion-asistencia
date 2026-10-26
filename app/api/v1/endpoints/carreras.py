"""Endpoints de Carrera: /api/v1/carreras (solo administrador)."""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.api.errores import manejar_integridad, obtener_o_404
from app.crud import base as crud
from app.models.carrera import Carrera
from app.models.usuario import Rol
from app.schemas.carrera import CarreraCreate, CarreraRead, CarreraUpdate

router = APIRouter(prefix="/carreras", dependencies=[Depends(requiere_rol(Rol.admin))])


def _obtener(session: SessionDep, carrera_id: int) -> Carrera:
    return obtener_o_404(crud.obtener(session, Carrera, carrera_id), "Carrera no encontrada")


@router.post("/", response_model=CarreraRead, status_code=status.HTTP_201_CREATED)
def crear(data: CarreraCreate, session: SessionDep):
    with manejar_integridad(session):
        return crud.crear(session, Carrera.model_validate(data))


@router.get("/", response_model=list[CarreraRead])
def listar(session: SessionDep, offset: int = 0, limit: int = Query(default=100, le=100)):
    return crud.listar(session, Carrera, offset=offset, limit=limit)


@router.get("/{carrera_id}", response_model=CarreraRead)
def obtener(carrera_id: int, session: SessionDep):
    return _obtener(session, carrera_id)


@router.patch("/{carrera_id}", response_model=CarreraRead)
def actualizar(carrera_id: int, data: CarreraUpdate, session: SessionDep):
    carrera = _obtener(session, carrera_id)
    with manejar_integridad(session):
        return crud.actualizar(session, carrera, data.model_dump(exclude_unset=True))


@router.delete("/{carrera_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(carrera_id: int, session: SessionDep):
    carrera = _obtener(session, carrera_id)
    with manejar_integridad(session, al_borrar=True):
        crud.borrar(session, carrera)
