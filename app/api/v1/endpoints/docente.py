"""Endpoints del docente: /api/v1/docente (HU-02)."""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import DocenteUser, SessionDep
from app.api.errores import manejar_integridad
from app.models.docente import Docente
from app.models.usuario import Usuario
from app.schemas.ausencia import AvisoCreate, AvisoRead, ClaseDisponible
from app.services import ausencias

router = APIRouter(prefix="/docente")


def _perfil(usuario: Usuario) -> Docente:
    if usuario.docente is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario no tiene perfil de docente")
    return usuario.docente


@router.get("/clases-disponibles", response_model=list[ClaseDisponible])
def clases_disponibles(usuario: DocenteUser, session: SessionDep):
    """Próximas clases del docente sobre las que todavía puede avisar (próximos 7 días,
    al menos 1 hora antes del inicio, sin aviso cargado)."""
    return ausencias.clases_disponibles(session, _perfil(usuario))


@router.post("/avisos", response_model=AvisoRead, status_code=status.HTTP_201_CREATED)
def registrar_aviso(data: AvisoCreate, usuario: DocenteUser, session: SessionDep):
    """Registra el aviso de que el docente no va a dar la clase (cátedra + fecha)."""
    docente = _perfil(usuario)
    try:
        with manejar_integridad(session):
            return ausencias.registrar_aviso(session, docente, data.catedra_id, data.fecha)
    except ausencias.CatedraNoEncontrada:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cátedra no encontrada")
    except ausencias.AvisoInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
