"""Acceso a datos de Carrera."""
from sqlmodel import Session, select

from app.models.carrera import Carrera
from app.schemas.carrera import CarreraCreate, CarreraUpdate


def crear(session: Session, data: CarreraCreate) -> Carrera:
    carrera = Carrera.model_validate(data)
    session.add(carrera)
    session.commit()
    session.refresh(carrera)
    return carrera


def listar(session: Session, offset: int = 0, limit: int = 100) -> list[Carrera]:
    return list(session.exec(select(Carrera).order_by(Carrera.id).offset(offset).limit(limit)))


def obtener(session: Session, carrera_id: int) -> Carrera | None:
    return session.get(Carrera, carrera_id)


def actualizar(session: Session, carrera: Carrera, data: CarreraUpdate) -> Carrera:
    carrera.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(carrera)
    session.commit()
    session.refresh(carrera)
    return carrera


def borrar(session: Session, carrera: Carrera) -> None:
    session.delete(carrera)
    session.commit()
