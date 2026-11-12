"""Contrato de robustez de las rutas implementadas, sobre la app ASGI real.

Se usa /openapi.json generado: el YAML formal también incluye alcance futuro.
Este smoke test comprueba robustez; test_convergencia_con72.py valida respuestas
y eventos contra los contratos publicados. No se inyectan tokens:
las rutas protegidas ejercitan rechazos y las públicas sus implementaciones.
"""

import os

import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ["AUTH_STRICT_ENFORCEMENT"] = "true"

from src.core.config import settings as app_settings
from src.core.database import get_db_session
from src.main import app

# Cada ejemplo de Schemathesis corre en un event loop distinto: compartir pool
# reutilizaría conexiones asyncpg ligadas a un loop cerrado.
_engine = create_async_engine(app_settings.DATABASE_URL, poolclass=NullPool)
_sessions = async_sessionmaker(_engine, expire_on_commit=False)


async def _sesion_por_peticion():
    async with _sessions() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db_session] = _sesion_por_peticion

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize()
@settings(
    max_examples=10,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_api_no_devuelve_errores_de_servidor(case):
    case.call_and_validate(checks=[not_a_server_error])
