"""Endpoints de Inscripción: /api/v1/inscripciones (solo administrador).

Para dar de baja una inscripción sin perder el registro: PATCH {"vigente": false}.
"""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.api.errores import manejar_integridad, obtener_o_404
from app.crud import base as crud
from app.models.inscripcion import Inscripcion
from app.models.usuario import Rol
from app.schemas.inscripcion import InscripcionCreate, InscripcionRead, InscripcionUpdate

router = APIRouter(prefix="/inscripciones", dependencies=[Depends(requiere_rol(Rol.admin))])


def _obtener(session: SessionDep, inscripcion_id: int) -> Inscripcion:
    return obtener_o_404(crud.obtener(session, Inscripcion, inscripcion_id), "Inscripción no encontrada")


@router.post("/", response_model=InscripcionRead, status_code=status.HTTP_201_CREATED)
def crear(data: InscripcionCreate, session: SessionDep):
    with manejar_integridad(session):
        return crud.crear(session, Inscripcion.model_validate(data))


@router.get("/", response_model=list[InscripcionRead])
def listar(
    session: SessionDep,
    alumno_id: int | None = None,
    catedra_id: int | None = None,
    vigente: bool | None = None,
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    filtros = []
    if alumno_id is not None:
        filtros.append(Inscripcion.alumno_id == alumno_id)
    if catedra_id is not None:
        filtros.append(Inscripcion.catedra_id == catedra_id)
    if vigente is not None:
        filtros.append(Inscripcion.vigente == vigente)
    return crud.listar(session, Inscripcion, *filtros, offset=offset, limit=limit)


@router.get("/{inscripcion_id}", response_model=InscripcionRead)
def obtener(inscripcion_id: int, session: SessionDep):
    return _obtener(session, inscripcion_id)


@router.patch("/{inscripcion_id}", response_model=InscripcionRead)
def actualizar(inscripcion_id: int, data: InscripcionUpdate, session: SessionDep):
    inscripcion = _obtener(session, inscripcion_id)
    with manejar_integridad(session):
        return crud.actualizar(session, inscripcion, data.model_dump(exclude_unset=True))


@router.delete("/{inscripcion_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(inscripcion_id: int, session: SessionDep):
    inscripcion = _obtener(session, inscripcion_id)
    with manejar_integridad(session, al_borrar=True):
        crud.borrar(session, inscripcion)
