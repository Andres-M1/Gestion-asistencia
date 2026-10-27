"""Endpoints del alumno: /api/v1/alumno (HU-05, HU-07)."""
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import EstudianteUser, SessionDep
from app.models.alumno import Alumno
from app.models.usuario import Usuario
from app.schemas.ausencia import AvisoDetalle
from app.schemas.inscripcion import MiInscripcion
from app.services import ausencias, inscripciones

router = APIRouter(prefix="/alumno")


def _perfil(usuario: Usuario) -> Alumno:
    if usuario.alumno is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario no tiene perfil de alumno")
    return usuario.alumno


@router.get("/inscripciones", response_model=list[MiInscripcion])
def mis_inscripciones(usuario: EstudianteUser, session: SessionDep):
    """Inscripciones vigentes del alumno logueado, con materia, comisión, horario y docente (HU-07)."""
    return inscripciones.inscripciones_vigentes(session, _perfil(usuario))


@router.get("/avisos", response_model=list[AvisoDetalle])
def mis_avisos(
    usuario: EstudianteUser,
    session: SessionDep,
    catedra_id: int | None = None,
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    """Avisos de hoy en adelante de las cátedras donde el alumno tiene inscripción vigente,
    del más próximo al más lejano (HU-05). Con ?catedra_id=, solo los de esa cátedra."""
    try:
        return ausencias.avisos_del_alumno(session, _perfil(usuario), catedra_id, offset, limit)
    except ausencias.SinInscripcionVigente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tenés una inscripción vigente en esa cátedra")
