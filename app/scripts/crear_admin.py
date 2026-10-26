"""Crea un usuario administrador.

Uso (parado en la raíz del proyecto):
    python -m app.scripts.crear_admin --dni 12345678
    docker compose exec web python -m app.scripts.crear_admin --dni 12345678

La contraseña se pide por teclado (no queda en el historial de la terminal).
"""
import argparse
import getpass
import sys

from sqlmodel import Session

from app.core.database import engine
from app.crud import usuario as crud_usuario
from app.models.usuario import Rol


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear un usuario administrador")
    parser.add_argument("--dni", required=True)
    args = parser.parse_args()

    with Session(engine) as session:
        if crud_usuario.obtener_por_dni(session, args.dni):
            sys.exit(f"Ya existe un usuario con DNI {args.dni}")

        password = getpass.getpass("Contraseña: ")
        if len(password) < 8:
            sys.exit("La contraseña debe tener al menos 8 caracteres")
        if password != getpass.getpass("Repetir contraseña: "):
            sys.exit("Las contraseñas no coinciden")

        usuario = crud_usuario.crear(session, args.dni, password, Rol.admin)
        print(f"Administrador creado (id={usuario.id}, dni={usuario.dni})")


if __name__ == "__main__":
    main()
