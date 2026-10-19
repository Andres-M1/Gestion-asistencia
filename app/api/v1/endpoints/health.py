"""Endpoint de salud: verifica que la API y la base de datos respondan."""
from fastapi import APIRouter
from sqlmodel import text

from app.api.deps import SessionDep

router = APIRouter()


@router.get("/health")
def health(session: SessionDep) -> dict:
    session.exec(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
