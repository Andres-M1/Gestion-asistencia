"""Endpoints de Alumno: /api/v1/alumnos (solo administrador, HU-08).

No hay DELETE: para que un alumno no pueda entrar más se lo desactiva con
PATCH {"activo": false}.
"""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.api.errores import manejar_integridad, obtener_o_404
from app.crud import base as crud
from app.models.alumno import Alumno
from app.models.usuario import Rol
from app.schemas.persona import AlumnoCreate, AlumnoRead, AlumnoUpdate
from app.services import personas

router = APIRouter(prefix="/alumnos", dependencies=[Depends(requiere_rol(Rol.admin))])


def _obtener(session: SessionDep, alumno_id: int) -> Alumno:
    return obtener_o_404(crud.obtener(session, Alumno, alumno_id), "Alumno no encontrado")


@router.post("/", response_model=AlumnoRead, status_code=status.HTTP_201_CREATED)
def crear(data: AlumnoCreate, session: SessionDep):
    with manejar_integridad(session):
        return personas.a_dict(personas.crear(session, Alumno, Rol.estudiante, data))


@router.get("/", response_model=list[AlumnoRead])
def listar(
    session: SessionDep,
    carrera_id: int | None = None,
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    filtros = [Alumno.carrera_id == carrera_id] if carrera_id is not None else []
    return [personas.a_dict(a) for a in crud.listar(session, Alumno, *filtros, offset=offset, limit=limit)]


@router.get("/{alumno_id}", response_model=AlumnoRead)
def obtener(alumno_id: int, session: SessionDep):
    return personas.a_dict(_obtener(session, alumno_id))


@router.patch("/{alumno_id}", response_model=AlumnoRead)
def actualizar(alumno_id: int, data: AlumnoUpdate, session: SessionDep):
    alumno = _obtener(session, alumno_id)
    with manejar_integridad(session):
        return personas.a_dict(personas.actualizar(session, alumno, data))
