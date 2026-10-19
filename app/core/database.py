"""Conexión a PostgreSQL: engine de SQLAlchemy y sesiones de SQLModel."""
from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True)


def get_session() -> Generator[Session, None, None]:
    """Abre una sesión por request y la cierra al terminar."""
    with Session(engine) as session:
        yield session
