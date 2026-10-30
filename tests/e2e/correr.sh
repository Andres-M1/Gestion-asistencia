#!/usr/bin/env bash
# Corre los tests end-to-end contra una API levantada en un stack de Docker aparte.
#
# Uso (desde cualquier carpeta):  tests/e2e/correr.sh
#
# 1. Levanta base + API con el proyecto de Docker "gestion_asist_e2e" (no toca
#    los contenedores ni la base de desarrollo). La API queda en el puerto
#    E2E_PUERTO (por defecto 8001).
# 2. Carga los datos de prueba (incluye el admin 11111111 / prueba123).
# 3. Corre pytest -m e2e.
# 4. Al terminar, bien o mal, apaga todo y borra los datos.
set -euo pipefail

cd "$(dirname "$0")/../.."

export E2E_PUERTO="${E2E_PUERTO:-8001}"
export E2E_BASE_URL="http://localhost:${E2E_PUERTO}"
compose=(docker compose -p gestion_asist_e2e -f tests/e2e/docker-compose.yml)

# Python con pytest y httpx: el del .venv si existe, si no el del sistema
python="${PYTHON:-python3}"
if [[ -z "${PYTHON:-}" && -x .venv/bin/python ]]; then
    python=.venv/bin/python
fi

apagar() {
    echo "==> Apagando el stack e2e"
    "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap apagar EXIT

echo "==> Levantando base y API (puerto ${E2E_PUERTO})"
if ! "${compose[@]}" up -d --build --wait; then
    "${compose[@]}" logs api
    exit 1
fi

echo "==> Cargando datos de prueba"
"${compose[@]}" exec -T api python -m app.scripts.cargar_datos_prueba >/dev/null

echo "==> Corriendo los tests e2e contra ${E2E_BASE_URL}"
estado=0
"$python" -m pytest tests/e2e -m e2e --no-cov --confcutdir=tests/e2e -p no:cacheprovider "$@" || estado=$?

if [[ $estado -ne 0 ]]; then
    echo "==> Últimas líneas del log de la API"
    "${compose[@]}" logs --tail 50 api
fi
exit $estado
