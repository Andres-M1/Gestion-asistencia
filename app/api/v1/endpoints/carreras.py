"""Endpoints de Carrera: /api/v1/carreras"""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep
from app.crud import carrera as crud
from app.models.carrera import Carrera
from app.schemas.carrera import CarreraCreate, CarreraRead, CarreraUpdate

router = APIRouter(prefix="/carreras")


def _obtener_o_404(session: SessionDep, carrera_id: int) -> Carrera:
    carrera = crud.obtener(session, carrera_id)
    if carrera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Carrera no encontrada")
    return carrera


@router.post("/", response_model=CarreraRead, status_code=status.HTTP_201_CREATED)
def crear(data: CarreraCreate, session: SessionDep):
    try:
        return crud.crear(session, data)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una carrera con ese nombre")


@router.get("/", response_model=list[CarreraRead])
def listar(session: SessionDep, offset: int = 0, limit: int = Query(default=100, le=100)):
    return crud.listar(session, offset, limit)


@router.get("/{carrera_id}", response_model=CarreraRead)
def obtener(carrera_id: int, session: SessionDep):
    return _obtener_o_404(session, carrera_id)


@router.patch("/{carrera_id}", response_model=CarreraRead)
def actualizar(carrera_id: int, data: CarreraUpdate, session: SessionDep):
    carrera = _obtener_o_404(session, carrera_id)
    try:
        return crud.actualizar(session, carrera, data)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una carrera con ese nombre")


@router.delete("/{carrera_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(carrera_id: int, session: SessionDep):
    carrera = _obtener_o_404(session, carrera_id)
    try:
        crud.borrar(session, carrera)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede borrar: la carrera tiene materias o alumnos")
