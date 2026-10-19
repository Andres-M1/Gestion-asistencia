# Gestion Asist

Aplicación web construida con **FastAPI**, **SQLModel** (ORM) y **PostgreSQL**.

## Tecnologías

| Herramienta        | Para qué se usa                                                        |
|--------------------|------------------------------------------------------------------------|
| FastAPI            | Framework web: rutas, validación, documentación automática (`/docs`).  |
| SQLModel           | ORM: define las tablas como clases Python (une SQLAlchemy + Pydantic). |
| PostgreSQL         | Base de datos relacional.                                              |
| psycopg (v3)       | Driver que conecta Python con PostgreSQL.                              |
| Alembic            | Migraciones: versiona los cambios en la estructura de la base.        |
| pydantic-settings  | Lee la configuración desde el archivo `.env`.                          |
| Jinja2             | Plantillas HTML para las páginas web (incluido en `fastapi[standard]`). |
| pytest             | Tests automáticos.                                                     |
| Docker / Compose   | Corre la app y PostgreSQL en contenedores, igual en cualquier máquina. |

## Estructura de carpetas

```
Gestion_asist/
├── .venv/                    # Entorno virtual de Python (no se sube a git)
├── .env                      # Variables de entorno reales (no se sube a git)
├── .env.example              # Plantilla de .env para otros desarrolladores
├── .gitignore                # Archivos que git debe ignorar
├── requirements.txt          # Dependencias con versión fija
├── Dockerfile                # Receta de la imagen de la app (Python + dependencias + código)
├── docker-compose.yml        # Levanta los servicios "db" (PostgreSQL) y "web" (FastAPI)
├── .dockerignore             # Archivos que no se copian a la imagen
├── alembic.ini               # Configuración de Alembic
├── alembic/                  # Migraciones de base de datos
│   ├── env.py                # Conecta Alembic con la config y los modelos de SQLModel
│   ├── script.py.mako        # Plantilla de cada archivo de migración
│   └── versions/             # Archivos de migración generados
├── app/                      # Código de la aplicación
│   ├── main.py               # Punto de entrada: crea la app FastAPI y registra rutas
│   ├── core/                 # Configuración central
│   │   ├── config.py         # Settings (lee .env) y arma la DATABASE_URL
│   │   └── database.py       # Engine de la BD y función get_session()
│   ├── models/               # Modelos ORM = tablas de la base de datos
│   │   └── __init__.py       # Importar aquí cada modelo para que Alembic lo detecte
│   ├── schemas/              # Esquemas de entrada/salida de la API (qué recibe y devuelve)
│   ├── crud/                 # Funciones de acceso a datos (crear, leer, actualizar, borrar)
│   ├── services/             # Lógica de negocio (reglas que combinan varios CRUD)
│   ├── api/                  # Capa HTTP
│   │   ├── deps.py           # Dependencias comunes (ej. SessionDep = sesión de BD)
│   │   └── v1/               # Versión 1 de la API (prefijo /api/v1)
│   │       ├── router.py     # Junta todos los routers de endpoints
│   │       └── endpoints/    # Un archivo por recurso (health.py, alumnos.py, ...)
│   ├── templates/            # Plantillas HTML (Jinja2)
│   │   ├── base.html         # Layout común
│   │   └── index.html        # Página de inicio
│   └── static/               # Archivos estáticos servidos en /static
│       ├── css/
│       ├── js/
│       └── img/
└── tests/                    # Tests con pytest
```

### Cómo fluye un request

```
Navegador / cliente
   → api/v1/endpoints/*.py    (recibe el request, valida con schemas/)
   → services/*.py            (aplica reglas de negocio, si las hay)
   → crud/*.py                (consulta/modifica la BD usando models/)
   → PostgreSQL
```

Separar en capas hace que cada archivo tenga una sola responsabilidad: los endpoints no escriben SQL y los CRUD no saben nada de HTTP.

## Puesta en marcha (con Docker)

Todo corre en Docker y hay **una sola base de datos**: la del contenedor `db`.

| Desde dónde                                  | Cómo se llega a la base               |
|----------------------------------------------|---------------------------------------|
| Contenedor `web` (la app)                    | `db:5432` (red interna de Docker)     |
| Tu máquina (`.venv`, `alembic`, DBeaver, `psql`) | `localhost:5433`                  |

`docker-compose.yml` pisa `POSTGRES_HOST` y `POSTGRES_PORT` para el contenedor `web`, así que el `.env` siempre queda con `localhost` / `5433`.

> **¿WSL?** Solo hace falta en Windows: abrir una terminal de WSL, tener Docker Desktop con integración WSL y seguir estos mismos pasos. En Linux no se necesita.

### 1. Configurar variables de entorno

```bash
cp .env.example .env   # si todavía no existe
```

Editá usuario, contraseña y nombre de base. La primera vez que arranca, el contenedor de PostgreSQL **crea solo** ese usuario y esa base (no hace falta `psql` ni `sudo`).

> Si cambiás usuario o contraseña después de la primera vez, no se aplica: los datos ya existen en el volumen. Hay que borrarlo con `docker compose down -v` (**borra todos los datos**).

### 2. Levantar todo

```bash
docker compose up --build
```

Esto construye la imagen, arranca la base, espera a que esté lista, aplica las migraciones (`alembic upgrade head`) y levanta FastAPI con recarga automática.

- Página web: http://localhost:8000
- Documentación interactiva de la API: http://localhost:8000/docs
- Chequeo de salud (API + BD): http://localhost:8000/api/v1/health

Para detener: `Ctrl+C` o, si lo levantaste con `-d`, `docker compose down`.

### 3. Entorno virtual local (para el editor y los comandos)

El `.venv` sirve para que VS Code autocomplete y para correr `alembic` o `pytest` desde tu máquina contra la misma base del contenedor:

```bash
python3 -m venv .venv          # solo la primera vez
source .venv/bin/activate
pip install -r requirements.txt
```

Todos los comandos se ejecutan **parado en la carpeta raíz del proyecto** (donde están `app/`, `.env` y `docker-compose.yml`).

## Agregar una tabla nueva (ejemplo: `Alumno`)

1. **Modelo** — `app/models/alumno.py`:

   ```python
   from sqlmodel import Field, SQLModel

   class Alumno(SQLModel, table=True):
       id: int | None = Field(default=None, primary_key=True)
       nombre: str
       email: str = Field(unique=True)
   ```

2. **Registrarlo** en `app/models/__init__.py`:

   ```python
   from app.models.alumno import Alumno  # noqa: F401
   ```

3. **Schemas** — `app/schemas/alumno.py` (lo que entra y sale por la API):

   ```python
   from sqlmodel import SQLModel

   class AlumnoCreate(SQLModel):
       nombre: str
       email: str

   class AlumnoRead(SQLModel):
       id: int
       nombre: str
       email: str
   ```

4. **CRUD** — `app/crud/alumno.py`:

   ```python
   from sqlmodel import Session, select
   from app.models.alumno import Alumno
   from app.schemas.alumno import AlumnoCreate

   def crear(session: Session, data: AlumnoCreate) -> Alumno:
       alumno = Alumno.model_validate(data)
       session.add(alumno)
       session.commit()
       session.refresh(alumno)
       return alumno

   def listar(session: Session) -> list[Alumno]:
       return list(session.exec(select(Alumno)))
   ```

5. **Endpoint** — `app/api/v1/endpoints/alumnos.py`:

   ```python
   from fastapi import APIRouter
   from app.api.deps import SessionDep
   from app.crud import alumno as crud
   from app.schemas.alumno import AlumnoCreate, AlumnoRead

   router = APIRouter(prefix="/alumnos")

   @router.post("/", response_model=AlumnoRead)
   def crear(data: AlumnoCreate, session: SessionDep):
       return crud.crear(session, data)

   @router.get("/", response_model=list[AlumnoRead])
   def listar(session: SessionDep):
       return crud.listar(session)
   ```

6. **Registrar el router** en `app/api/v1/router.py`:

   ```python
   from app.api.v1.endpoints import alumnos
   api_router.include_router(alumnos.router, tags=["alumnos"])
   ```

7. **Crear y aplicar la migración**:

   ```bash
   alembic revision --autogenerate -m "crear tabla alumno"
   alembic upgrade head
   ```

## Comandos útiles

### Docker

| Comando                                              | Qué hace                                         |
|------------------------------------------------------|--------------------------------------------------|
| `docker compose up --build`                          | Construye y levanta base + app (ver logs en vivo) |
| `docker compose up -d`                               | Levanta en segundo plano                         |
| `docker compose logs -f web`                         | Muestra los logs de la app                       |
| `docker compose ps`                                  | Lista los contenedores y su estado               |
| `docker compose down`                                | Detiene los contenedores (los datos se conservan) |
| `docker compose down -v`                             | Detiene y **borra la base de datos**             |
| `docker compose exec db psql -U gestion_asist -d gestion_asist` | Abre `psql` dentro de la base        |
| `docker compose exec web alembic upgrade head`       | Aplica migraciones dentro del contenedor         |

### Python / Alembic (con el `.venv` activo)

| Comando                                         | Qué hace                                   |
|-------------------------------------------------|--------------------------------------------|
| `source .venv/bin/activate`                     | Activa el entorno virtual                  |
| `deactivate`                                    | Sale del entorno virtual                   |
| `alembic revision --autogenerate -m "mensaje"`  | Genera una migración a partir de los modelos |
| `alembic upgrade head`                          | Aplica todas las migraciones pendientes    |
| `alembic downgrade -1`                          | Revierte la última migración               |
| `alembic history`                               | Muestra el historial de migraciones        |
| `pytest`                                        | Ejecuta los tests                          |

Para agregar una dependencia: `pip install <paquete>`, sumarla con su versión a `requirements.txt` y reconstruir con `docker compose up --build`.
