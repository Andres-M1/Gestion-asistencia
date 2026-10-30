"""Fixtures de los tests end-to-end.

Le pegan por HTTP a una API levantada (E2E_BASE_URL) con los datos de
app/scripts/cargar_datos_prueba.py. No importan nada de app/: prueban la API
como la usan la app Android y la web. Se corren con tests/e2e/correr.sh.

¡Registran avisos de verdad! Nunca apuntar E2E_BASE_URL a una base con datos reales.
"""
import os

import httpx
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
PASSWORD = "prueba123"

# Usuarios de cargar_datos_prueba.py
ADMIN = "11111111"
DOCENTE = "22222222"        # Laura Gómez
OTRO_DOCENTE = "22222223"   # Martín Pérez
ALUMNOS = ["33333331", "33333332", "33333333", "33333334", "33333335", "33333336"]


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=f"{BASE_URL}/api/v1", timeout=10) as cliente:
        try:
            cliente.get("/health").raise_for_status()
        except httpx.HTTPError as e:
            pytest.exit(f"La API no responde en {BASE_URL} ({e}). ¿Corriste tests/e2e/correr.sh?", returncode=2)
        yield cliente


@pytest.fixture(scope="session")
def login(api):
    """login(dni) -> encabezado Authorization. Hace un solo login por DNI."""
    tokens = {}

    def _login(dni: str) -> dict:
        if dni not in tokens:
            r = api.post("/auth/login", json={"dni": dni, "password": PASSWORD})
            assert r.status_code == 200, f"login {dni}: {r.status_code} {r.text}"
            tokens[dni] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return tokens[dni]

    return _login
