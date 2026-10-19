"""Agrupa todos los routers de la versión 1 de la API."""
from fastapi import APIRouter

from app.api.v1.endpoints import carreras, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(carreras.router, tags=["carreras"])
