"""Carga datos de prueba en la base de desarrollo (herramienta de desarrollo, no es una HU).

Uso (parado en la raíz del proyecto):
    docker compose exec web python -m app.scripts.cargar_datos_prueba

Es idempotente: si un dato ya existe (por DNI, nombre, materia + comisión, etc.)
lo saltea sin modificarlo, así se puede correr varias veces.
Todos los usuarios tienen la contraseña PASSWORD. Los emails usan @example.com, un dominio
reservado que nunca entrega correo: probar las notificaciones (HU-06) no le escribe a nadie.
"""
import sys
from datetime import time

from sqlmodel import Session, select

from app.core.database import engine
from app.core.security import verify_password
from app.crud import base as crud
from app.crud import usuario as crud_usuario
from app.models.alumno import Alumno
from app.models.carrera import Carrera
from app.models.catedra import Catedra
from app.models.docente import Docente
from app.models.inscripcion import Inscripcion
from app.models.materia import Materia
from app.models.usuario import Rol
from app.schemas.persona import AlumnoCreate, DocenteCreate
from app.services import personas

PASSWORD = "prueba123"

ADMIN = {"dni": "11111111", "email": "preceptor@example.com"}

CARRERAS = {
    "Desarrollo de Software": ["Programación I", "Base de Datos"],
    "Análisis de Sistemas": ["Análisis de Sistemas I", "Sistemas Operativos"],
}

DOCENTES = [
    ("22222222", "Laura", "Gómez"),
    ("22222223", "Martín", "Pérez"),
]

# (dni, nombre, apellido, carrera)
ALUMNOS = [
    ("33333331", "Sofía", "Díaz", "Desarrollo de Software"),
    ("33333332", "Lucas", "Fernández", "Desarrollo de Software"),
    ("33333333", "Valentina", "López", "Desarrollo de Software"),
    ("33333334", "Mateo", "Romero", "Análisis de Sistemas"),
    ("33333335", "Camila", "Sosa", "Análisis de Sistemas"),
    ("33333336", "Joaquín", "Torres", "Análisis de Sistemas"),
]

# (materia, comisión, dni docente, día 1=lunes..7=domingo, inicio, fin)
CATEDRAS = [
    ("Programación I", "1K1", "22222222", 1, time(18, 0), time(20, 0)),
    ("Programación I", "1K2", "22222223", 2, time(18, 0), time(20, 0)),
    ("Base de Datos", "1K1", "22222222", 3, time(18, 0), time(20, 0)),
    ("Análisis de Sistemas I", "2K1", "22222222", 4, time(14, 0), time(16, 0)),
    ("Sistemas Operativos", "2K1", "22222223", 6, time(9, 0), time(11, 0)),
]

# (dni alumno, materia, comisión, vigente)
INSCRIPCIONES = [
    ("33333331", "Programación I", "1K1", True),
    ("33333331", "Base de Datos", "1K1", True),
    ("33333331", "Programación I", "1K2", False),  # se cambió de comisión: para probar HU-05/07
    ("33333332", "Programación I", "1K1", True),
    ("33333332", "Base de Datos", "1K1", True),
    ("33333333", "Programación I", "1K2", True),
    ("33333333", "Base de Datos", "1K1", True),
    ("33333334", "Análisis de Sistemas I", "2K1", True),
    ("33333334", "Sistemas Operativos", "2K1", True),
    ("33333335", "Análisis de Sistemas I", "2K1", True),
    ("33333335", "Sistemas Operativos", "2K1", True),
    ("33333336", "Análisis de Sistemas I", "2K1", True),
    ("33333336", "Sistemas Operativos", "2K1", True),
]

creados = salteados = 0


def _contar(nuevo: bool) -> None:
    global creados, salteados
    if nuevo:
        creados += 1
    else:
        salteados += 1


def _primero(session: Session, modelo, *filtros):
    return session.exec(select(modelo).where(*filtros)).first()


def cargar_admin(session: Session) -> None:
    existe = crud_usuario.obtener_por_dni(session, ADMIN["dni"]) is not None
    if not existe:
        admin = crud_usuario.crear(session, ADMIN["dni"], PASSWORD, Rol.admin)
        crud.actualizar(session, admin, {"email": ADMIN["email"]})
    _contar(not existe)


def cargar_carreras_y_materias(session: Session) -> dict[str, Materia]:
    materias = {}
    for nombre_carrera, nombres_materias in CARRERAS.items():
        carrera = _primero(session, Carrera, Carrera.nombre == nombre_carrera)
        _contar(carrera is None)
        if carrera is None:
            carrera = crud.crear(session, Carrera(nombre=nombre_carrera))
        for nombre in nombres_materias:
            materia = _primero(session, Materia, Materia.carrera_id == carrera.id, Materia.nombre == nombre)
            _contar(materia is None)
            if materia is None:
                materia = crud.crear(session, Materia(carrera_id=carrera.id, nombre=nombre))
            materias[nombre] = materia
    return materias


def cargar_docentes(session: Session) -> dict[str, Docente]:
    docentes = {}
    for dni, nombre, apellido in DOCENTES:
        usuario = crud_usuario.obtener_por_dni(session, dni)
        _contar(usuario is None)
        if usuario is None:
            data = DocenteCreate(dni=dni, password=PASSWORD, nombre=nombre, apellido=apellido,
                                 email=f"docente.{dni}@example.com")
            docentes[dni] = personas.crear(session, Docente, Rol.docente, data)
        elif usuario.docente is None:
            sys.exit(f"El DNI {dni} ya existe pero no es un docente")
        else:
            docentes[dni] = usuario.docente
    return docentes


def cargar_alumnos(session: Session) -> dict[str, Alumno]:
    alumnos = {}
    for dni, nombre, apellido, nombre_carrera in ALUMNOS:
        usuario = crud_usuario.obtener_por_dni(session, dni)
        _contar(usuario is None)
        if usuario is None:
            carrera = _primero(session, Carrera, Carrera.nombre == nombre_carrera)
            data = AlumnoCreate(dni=dni, password=PASSWORD, nombre=nombre, apellido=apellido,
                                email=f"alumno.{dni}@example.com", carrera_id=carrera.id)
            alumnos[dni] = personas.crear(session, Alumno, Rol.estudiante, data)
        elif usuario.alumno is None:
            sys.exit(f"El DNI {dni} ya existe pero no es un alumno")
        else:
            alumnos[dni] = usuario.alumno
    return alumnos


def cargar_catedras(session: Session, materias: dict[str, Materia],
                    docentes: dict[str, Docente]) -> dict[tuple[str, str], Catedra]:
    catedras = {}
    for nombre_materia, comision, dni_docente, dia, inicio, fin in CATEDRAS:
        materia = materias[nombre_materia]
        catedra = _primero(session, Catedra, Catedra.materia_id == materia.id, Catedra.comision == comision)
        _contar(catedra is None)
        if catedra is None:
            catedra = crud.crear(session, Catedra(
                materia_id=materia.id, docente_id=docentes[dni_docente].id, comision=comision,
                dia_semana=dia, hora_inicio=inicio, hora_fin=fin,
            ))
        catedras[(nombre_materia, comision)] = catedra
    return catedras


def cargar_inscripciones(session: Session, alumnos: dict[str, Alumno],
                         catedras: dict[tuple[str, str], Catedra]) -> None:
    for dni, nombre_materia, comision, vigente in INSCRIPCIONES:
        alumno, catedra = alumnos[dni], catedras[(nombre_materia, comision)]
        existe = _primero(session, Inscripcion, Inscripcion.alumno_id == alumno.id,
                          Inscripcion.catedra_id == catedra.id) is not None
        _contar(not existe)
        if not existe:
            crud.crear(session, Inscripcion(alumno_id=alumno.id, catedra_id=catedra.id, vigente=vigente))


def imprimir_usuarios(session: Session, docentes: dict[str, Docente], alumnos: dict[str, Alumno]) -> None:
    filas = [(ADMIN["dni"], "admin", "Preceptor (sin perfil)")]
    filas += [(dni, "docente", f"{d.nombre} {d.apellido}") for dni, d in docentes.items()]
    filas += [(dni, "estudiante", f"{a.nombre} {a.apellido}") for dni, a in alumnos.items()]

    encabezado = ("DNI", "Rol", "Nombre", "Contraseña")

    def contraseña(dni: str) -> str:
        # Un usuario que ya existía antes del script puede tener otra contraseña
        usuario = crud_usuario.obtener_por_dni(session, dni)
        return PASSWORD if verify_password(PASSWORD, usuario.password_hash) else "(otra: ya existía)"

    filas = [(*f, contraseña(f[0])) for f in filas]
    anchos = [max(len(str(x)) for x in col) for col in zip(encabezado, *filas)]
    linea = "+".join("-" * (a + 2) for a in anchos)
    print(linea)
    print("|".join(f" {t:<{a}} " for t, a in zip(encabezado, anchos)))
    print(linea)
    for fila in filas:
        print("|".join(f" {t:<{a}} " for t, a in zip(fila, anchos)))
    print(linea)


def main() -> None:
    with Session(engine) as session:
        cargar_admin(session)
        materias = cargar_carreras_y_materias(session)
        docentes = cargar_docentes(session)
        alumnos = cargar_alumnos(session)
        catedras = cargar_catedras(session, materias, docentes)
        cargar_inscripciones(session, alumnos, catedras)

        print(f"Datos de prueba: {creados} creados, {salteados} ya existían (salteados).\n")
        imprimir_usuarios(session, docentes, alumnos)


if __name__ == "__main__":
    main()
