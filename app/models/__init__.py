"""Modelos ORM (tablas). Importar aquí cada modelo nuevo para que Alembic lo detecte."""
from sqlmodel import SQLModel  # noqa: F401

from app.models.alumno import Alumno  # noqa: F401
from app.models.ausencia import Ausencia  # noqa: F401
from app.models.carrera import Carrera  # noqa: F401
from app.models.catedra import Catedra  # noqa: F401
from app.models.docente import Docente  # noqa: F401
from app.models.inscripcion import Inscripcion  # noqa: F401
from app.models.materia import Materia  # noqa: F401
