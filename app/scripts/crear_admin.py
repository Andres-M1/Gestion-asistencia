"""Crea un usuario administrador.

Uso (parado en la raíz del proyecto):
    python -m app.scripts.crear_admin --dni 12345678 --email preceptor@instituto.edu.ar
    docker compose exec web python -m app.scripts.crear_admin --dni 12345678

La contraseña se pide por teclado (no queda en el historial de la terminal).
Si no se pasa --email, se pide por teclado (Enter para omitir). Sin email,
el preceptor no recibe los correos de avisos (HU-06).
"""
import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlmodel import Session

from app.core.database import engine
from app.crud import usuario as crud_usuario
from app.models.usuario import Rol


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear un usuario administrador")
    parser.add_argument("--dni", required=True)
    parser.add_argument("--email", help="Para recibir los correos de avisos (opcional)")
    args = parser.parse_args()

    with Session(engine) as session:
        if crud_usuario.obtener_por_dni(session, args.dni):
            sys.exit(f"Ya existe un usuario con DNI {args.dni}")

        password = getpass.getpass("Contraseña: ")
        if len(password) < 8:
            sys.exit("La contraseña debe tener al menos 8 caracteres")
        if password != getpass.getpass("Repetir contraseña: "):
            sys.exit("Las contraseñas no coinciden")

        email = args.email if args.email is not None else input("Email (Enter para omitir): ").strip()
        if email:
            try:
                email = TypeAdapter(EmailStr).validate_python(email)
            except ValidationError:
                sys.exit(f"Email inválido: {email}")

        usuario = crud_usuario.crear(session, args.dni, password, Rol.admin)
        if email:
            usuario.email = email
            session.add(usuario)
            session.commit()
        print(f"Administrador creado (id={usuario.id}, dni={usuario.dni}, email={email or 'sin email'})")


if __name__ == "__main__":
    main()
