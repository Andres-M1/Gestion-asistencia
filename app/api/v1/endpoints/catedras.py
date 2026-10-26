"""Endpoints de Cátedra: /api/v1/catedras (solo administrador).

Crear una cátedra = asignar un docente a una materia, con comisión y horario (HU-10).
"""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.api.errores import manejar_integridad, obtener_o_404
from app.crud import base as crud
from app.models.catedra import Catedra
from app.models.usuario import Rol
from app.schemas.catedra import CatedraCreate, CatedraRead, CatedraUpdate

router = APIRouter(prefix="/catedras", dependencies=[Depends(requiere_rol(Rol.admin))])


def _obtener(session: SessionDep, catedra_id: int) -> Catedra:
    return obtener_o_404(crud.obtener(session, Catedra, catedra_id), "Cátedra no encontrada")


@router.post("/", response_model=CatedraRead, status_code=status.HTTP_201_CREATED)
def crear(data: CatedraCreate, session: SessionDep):
    with manejar_integridad(session):
        return crud.crear(session, Catedra.model_validate(data))


@router.get("/", response_model=list[CatedraRead])
def listar(
    session: SessionDep,
    materia_id: int | None = None,
    docente_id: int | None = None,
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    filtros = []
    if materia_id is not None:
        filtros.append(Catedra.materia_id == materia_id)
    if docente_id is not None:
        filtros.append(Catedra.docente_id == docente_id)
    return crud.listar(session, Catedra, *filtros, offset=offset, limit=limit)


@router.get("/{catedra_id}", response_model=CatedraRead)
def obtener(catedra_id: int, session: SessionDep):
    return _obtener(session, catedra_id)


@router.patch("/{catedra_id}", response_model=CatedraRead)
def actualizar(catedra_id: int, data: CatedraUpdate, session: SessionDep):
    """También sirve para reasignar la cátedra a otro docente (docente_id)."""
    catedra = _obtener(session, catedra_id)
    with manejar_integridad(session):
        return crud.actualizar(session, catedra, data.model_dump(exclude_unset=True))


@router.delete("/{catedra_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(catedra_id: int, session: SessionDep):
    catedra = _obtener(session, catedra_id)
    with manejar_integridad(session, al_borrar=True):
        crud.borrar(session, catedra)
