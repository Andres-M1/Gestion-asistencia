"""Agrupa todos los routers de la versión 1 de la API."""
from fastapi import APIRouter

from app.api.v1.endpoints import alumnos, auth, carreras, catedras, docente, docentes, health, inscripciones, materias

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(docente.router, tags=["docente"])
api_router.include_router(carreras.router, tags=["admin: carreras"])
api_router.include_router(materias.router, tags=["admin: materias"])
api_router.include_router(docentes.router, tags=["admin: docentes"])
api_router.include_router(alumnos.router, tags=["admin: alumnos"])
api_router.include_router(catedras.router, tags=["admin: cátedras"])
api_router.include_router(inscripciones.router, tags=["admin: inscripciones"])
