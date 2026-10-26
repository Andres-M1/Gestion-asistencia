"""Operaciones CRUD genéricas, válidas para cualquier modelo de SQLModel."""
from typing import Any, TypeVar

from sqlmodel import Session, SQLModel, select

M = TypeVar("M", bound=SQLModel)


def crear(session: Session, obj: M) -> M:
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def obtener(session: Session, modelo: type[M], obj_id: int) -> M | None:
    return session.get(modelo, obj_id)


def listar(session: Session, modelo: type[M], *filtros: Any, offset: int = 0, limit: int = 100) -> list[M]:
    consulta = select(modelo).where(*filtros).order_by(modelo.id).offset(offset).limit(limit)
    return list(session.exec(consulta))


def actualizar(session: Session, obj: M, cambios: dict[str, Any]) -> M:
    obj.sqlmodel_update(cambios)
    return crear(session, obj)


def borrar(session: Session, obj: SQLModel) -> None:
    session.delete(obj)
    session.commit()
