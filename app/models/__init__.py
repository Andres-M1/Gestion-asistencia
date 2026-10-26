"""Modelos ORM (tablas). Importar aquí cada modelo nuevo para que Alembic lo detecte."""
from sqlmodel import SQLModel

# Nombres predecibles para restricciones e índices (Alembic los necesita para poder borrarlos)
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

from app.models.alumno import Alumno  # noqa: F401
from app.models.ausencia import Ausencia  # noqa: F401
from app.models.carrera import Carrera  # noqa: F401
from app.models.catedra import Catedra  # noqa: F401
from app.models.docente import Docente  # noqa: F401
from app.models.inscripcion import Inscripcion  # noqa: F401
from app.models.materia import Materia  # noqa: F401
from app.models.usuario import Usuario  # noqa: F401
