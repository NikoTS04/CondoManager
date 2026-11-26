"""Contrato de robustez de las rutas implementadas, sobre la app ASGI real.

Se usa /openapi.json generado: el YAML formal también incluye alcance futuro.
Este smoke test comprueba robustez; test_convergencia_con72.py valida respuestas
y eventos contra los contratos publicados. No se inyectan tokens:
las rutas protegidas ejercitan rechazos y las públicas sus implementaciones.
"""

import os

import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error

os.environ["AUTH_STRICT_ENFORCEMENT"] = "true"
# Readiness and route dependencies both use the application engine. Each
# Schemathesis example may run in a separate event loop.
os.environ["DB_NULL_POOL"] = "true"

from src.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app).exclude(
    path_regex=r"^/api/v1/jobs/(diario|notificaciones)$"
)


@schema.parametrize()
@settings(
    max_examples=10,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_api_no_devuelve_errores_de_servidor(case):
    case.call_and_validate(checks=[not_a_server_error])


def test_cron_rechaza_peticiones_sin_credencial_valida():
    # Schemathesis filtra ejemplos de Authorization en estas rutas.
    with TestClient(app) as client:
        for method, path in (
            ("GET", "/api/v1/jobs/diario"),
            ("POST", "/api/v1/jobs/notificaciones"),
        ):
            for headers in ({}, {"Authorization": "Basic invalid"}):
                response = client.request(method, path, headers=headers)
                assert response.status_code == 401
                assert response.json()["error_code"] == "CRON_NO_AUTORIZADO"
