# Guía de testing

Cómo correr los tests de la API, ver la cobertura y leer los resultados en GitHub. Los comandos se corren desde la raíz del proyecto.

## Resumen rápido

Desde la carpeta del proyecto, con Docker abierto y la base levantada (`docker compose up -d`):

| Quiero… | Comando | Si salió bien |
|---------|---------|---------------|
| Probar toda la API | `pytest` | `203 passed` |
| Probar el flujo completo, como la app | `tests/e2e/correr.sh` | `29 passed` |
| Probar un solo archivo | `pytest tests/test_hu02_avisos.py` | `passed` |

- Son **dos comandos**: `pytest` y `tests/e2e/correr.sh`.
- **No borran ni modifican** tus datos.
- En cada push o pull request a `main` se corren solos: el resultado está en la pestaña **Actions** (verde = bien).
- Si da error `pytest: orden no encontrada` (o `command not found`), primero: `source .venv/bin/activate`.

Si algo falla, mirá la sección "Si algo falla" más abajo.

## 1. Tipos de test

| Tipo | Dónde | Qué prueba | Cómo corre |
|------|-------|-----------|------------|
| **Tests de la API** | `tests/test_*.py` | Cada HU con sus criterios de aceptación: reglas de avisos, permisos, notificaciones (con SMTP y Firebase falsos) y errores. | Dentro del proceso, con `TestClient`, contra la base de Docker. Cada test se revierte al terminar: **no deja datos**. |
| **End-to-end (e2e)** | `tests/e2e/` | El flujo completo por HTTP, como lo usan la app y la web: login, registrar un aviso, quién lo ve y los errores 401/403/404/422. | Contra una API **levantada aparte** (proyecto de Docker `gestion_asist_e2e`, puerto 8001), con base limpia y sin SMTP ni Firebase. |
| **Cobertura** | — | Qué líneas de `app/` ejecutan los tests de la API. No cuenta `app/scripts/`: son herramientas de desarrollo (ver `.coveragerc`). | Sale sola al final de cada `pytest`. |

`pytest` corre solo los tests de la API. Los e2e están marcados con `e2e` y se corren con su script.

## 2. Qué hay que tener instalado

| Qué | Verificarlo con | Debería mostrar |
|-----|-----------------|-----------------|
| Docker y Docker Compose | `docker --version` y `docker compose version` | `Docker version 2x…` y `Docker Compose version v2…` o superior |
| Python 3.12 | `python3 --version` | `Python 3.12.x` |
| El `.venv` del proyecto con las dependencias | `source .venv/bin/activate` y después `pip show pytest-cov` | `Version: 7.1.0` |
| La base de desarrollo levantada (para los tests de la API) | `docker compose up -d` y después `docker compose ps` | `db` en estado `Up … (healthy)` |

Si falta el `.venv`, seguí la instalación del [README](../README.md#instalación). Si `pip show pytest-cov` no muestra nada: `pip install -r requirements.txt`.

## 3. Correr los tests

**Tests de la API + cobertura** (con el `.venv` activo):

```bash
pytest
```

También se puede dentro del contenedor: `docker compose exec web pytest`. Si sale bien, termina con la tabla de cobertura y el resumen:

```
app/services/ausencias.py                  89      1    99%   46
...
TOTAL                                    1009     20    98%
===================== 203 passed, 29 deselected in 43.73s ======================
```

- `29 deselected` son los e2e: es normal.
- Si aparecen `warnings`, no son errores. El aviso de firebase-admin sobre `MulticastMessage.tokens` está silenciado a propósito en `pytest.ini` (ver T30 en [decisiones.md](decisiones.md)).
- La columna `Missing` indica las líneas de cada archivo que ningún test ejecuta.

Variantes útiles:

| Comando | Para qué |
|---------|----------|
| `pytest tests/test_hu03_mis_avisos.py --no-cov -q` | Un solo archivo, sin la tabla de cobertura. |
| `pytest -k duplicado` | Solo los tests cuyo nombre contiene "duplicado". |
| `pytest --cov-report=html` | Además genera `htmlcov/index.html`: abrilo en el navegador para ver, línea por línea, qué está cubierto. |

**Tests end-to-end:**

```bash
tests/e2e/correr.sh
```

Tarda alrededor de 30 segundos (más la primera vez, porque construye la imagen). No hace falta tener levantado el `docker compose` de desarrollo, y **no lo toca**. Si sale bien:

```
==> Corriendo los tests e2e contra http://localhost:8001
tests/e2e/test_errores.py ...................                            [ 65%]
tests/e2e/test_flujo_aviso.py ..........                                 [100%]
============================== 29 passed in 2.47s ==============================
==> Apagando el stack e2e
```

Al final borra los contenedores y los datos del e2e, salga bien o mal. Los argumentos se pasan a pytest: `tests/e2e/correr.sh -k duplicado`.

## 4. Resultados en GitHub Actions

Cada push o pull request a `main` corre `.github/workflows/tests.yml`, con dos jobs:

- **pytest + cobertura**: los tests de la API contra un PostgreSQL 17 nuevo;
- **end-to-end**: `tests/e2e/correr.sh`.

Para ver los resultados:

1. En GitHub, abrí el repositorio y entrá a la pestaña **Actions**.
2. Elegí el workflow **Tests** y la ejecución de tu commit: ✅ verde, ❌ roja o 🟡 en curso.
3. Hacé clic en un job y desplegá el paso que falló (por ejemplo, **pytest con cobertura**) para ver la salida completa, con la tabla de cobertura.

El badge del principio del README muestra el estado de la última ejecución en `main`. En un pull request, los resultados aparecen abajo, en la sección de checks.

## 5. Si algo falla

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 5433 failed: Connection refused` | La base de desarrollo no está levantada. | `docker compose up -d` y esperar a que `docker compose ps` muestre `db` como `healthy`. |
| `pytest: error: unrecognized arguments: --cov=app --cov-report=term-missing` | Falta pytest-cov en el `.venv` o en la imagen del contenedor. | `.venv`: `pip install -r requirements.txt`. Contenedor: `docker compose up -d --build web`. |
| `ValidationError: 1 validation error for Settings` / `SECRET_KEY` / `Field required` | No hay `.env` (o le falta `SECRET_KEY`). | `cp .env.example .env` y completar `SECRET_KEY` (ver [Variables de entorno](../README.md#variables-de-entorno)). |
| El e2e falla con `failed to bind host port 0.0.0.0:8001/tcp: address already in use` | Otro programa usa el puerto 8001. | Usar otro: `E2E_PUERTO=8002 tests/e2e/correr.sh` |
| `failed to connect to the docker API … check if … the daemon is running` | Docker no está corriendo. | Abrir Docker Desktop (Windows) o `sudo systemctl start docker` (Linux). |
| Al correr los e2e con `pytest` directo: `La API no responde en http://localhost:8001` | Los e2e necesitan la API levantada. | Correrlos con `tests/e2e/correr.sh`. |

Si un test falla de verdad, pytest muestra el `assert` que no se cumplió, con el valor esperado y el obtenido. El e2e además muestra las últimas 50 líneas del log de la API.
