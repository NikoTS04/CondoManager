"""Fixtures de CON-04: migraciones y sesiones independientes en PostgreSQL real."""

import asyncio
import os
from dataclasses import dataclass
from importlib import import_module
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from scripts.seed_usuarios_demo import cargar_demo
from src.core.config import settings
from src.core.database import get_db_session
from src.main import app
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID

REVISIONES = (
    "20261008_0001_crear_condominios_y_auditoria",
    "20261008_0002_crear_presupuestos_mensuales",
    "20261014_0003_crear_configuracion_distribucion",
    "20261014_0004_crear_aplicaciones_saldo_favor",
    "20261018_0005_estructura_inmobiliaria",
    "20261019_0006_emision_cuotas",
    "20261020_0007_alta_usuarios",
    "20261020_0008_roles_revocables",
)


def migrar(connection, revisiones=REVISIONES):
    with Operations.context(MigrationContext.configure(connection)):
        for nombre in revisiones:
            import_module("migrations.versions." + nombre).upgrade()


@dataclass
class BaseUsuarios:
    engine: object
    sessions: object
    esquema: str
    url: str
    cid: str = str(CONDOMINIO_PILOTO_ID)


async def crear_base(url):
    esquema = "con04_" + uuid4().hex
    admin = create_async_engine(url, poolclass=NullPool)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
    await admin.dispose()
    engine = create_async_engine(
        url, poolclass=NullPool, connect_args={"server_settings": {"search_path": esquema}}
    )
    async with engine.begin() as conn:
        await conn.run_sync(migrar)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        await cargar_demo(session)
    return BaseUsuarios(engine, sessions, esquema, url)


async def borrar_base(base):
    await base.engine.dispose()
    admin = create_async_engine(base.url, poolclass=NullPool)
    async with admin.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA "{base.esquema}" CASCADE'))
    await admin.dispose()


@pytest.fixture
def db_usuarios(monkeypatch):
    url = (
        os.getenv("CON06_TEST_DATABASE_URL")
        or os.getenv("CON04_TEST_DATABASE_URL")
        or os.getenv("CON13_TEST_DATABASE_URL")
    )
    if not url:
        pytest.skip("Defina CON04_TEST_DATABASE_URL con una base PostgreSQL de pruebas.")
    base = asyncio.run(crear_base(url))
    monkeypatch.setattr(settings, "DEMO_MODE", True)

    async def session():
        async with base.sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    previous = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = session
    yield base
    if previous is None:
        app.dependency_overrides.pop(get_db_session, None)
    else:
        app.dependency_overrides[get_db_session] = previous
    asyncio.run(borrar_base(base))


@pytest_asyncio.fixture
async def api_usuarios(db_usuarios):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        yield client, db_usuarios


@pytest.fixture
def cliente_usuarios(db_usuarios):
    with TestClient(app) as client:
        yield client, db_usuarios
