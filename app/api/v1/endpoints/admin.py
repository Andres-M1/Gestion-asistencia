"""Endpoints del administrador / preceptor: /api/v1/admin (HU-09)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, requiere_rol
from app.models.usuario import Rol
from app.schemas.ausencia import AvisoDetalle
from app.services import ausencias

router = APIRouter(prefix="/admin", dependencies=[Depends(requiere_rol(Rol.admin))])


@router.get("/avisos", response_model=list[AvisoDetalle])
def listar_avisos(
    session: SessionDep,
    carrera_id: int | None = None,
    materia_id: int | None = None,
    comision: str | None = Query(default=None, description='Texto exacto, sin distinguir mayúsculas (ej. "1k1" = "1K1")'),
    docente_id: int | None = None,
    fecha_desde: date | None = Query(default=None, description="Inclusive"),
    fecha_hasta: date | None = Query(default=None, description="Inclusive"),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    """Todos los avisos, pasados y futuros, del más nuevo al más viejo. Los filtros se combinan entre sí."""
    if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "fecha_desde no puede ser posterior a fecha_hasta")
    return ausencias.avisos_filtrados(
        session,
        carrera_id=carrera_id,
        materia_id=materia_id,
        comision=comision,
        docente_id=docente_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        offset=offset,
        limit=limit,
    )
