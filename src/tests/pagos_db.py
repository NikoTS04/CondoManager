"""CON-70: PostgreSQL migrado y evidencia privada en directorio aislado por prueba."""

import asyncio
from datetime import date
from decimal import Decimal
from importlib import import_module
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient

from src.core.config import settings
from src.main import app
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.usuarios.piloto import vinculo_piloto


def migrar_pagos(connection):
    with Operations.context(MigrationContext.configure(connection)):
        import_module("migrations.versions.20261020_0009_pagos_persistentes").upgrade()


def did(numero="402"):
    return UUID(vinculo_piloto(numero, "PROPIETARIO_TITULAR")["departamento_id"])


async def preparar(base):
    async with base.sessions() as db, db.begin():
        db.add(
            CuotaMantenimiento(
                id=uuid4(),
                departamento_id=did(),
                periodo="2000-01",
                monto_ordinario=Decimal("150.00"),
                monto_extraordinario=Decimal("0.00"),
                monto_mora=Decimal("20.00"),
                monto_descuento=Decimal("0.00"),
                monto_total_exigible=Decimal("170.00"),
                monto_pagado=Decimal("0.00"),
                fecha_emision=date(2000, 1, 1),
                fecha_vencimiento=date(2000, 1, 20),
                estado="EN_MORA",
            )
        )
    await base.engine.dispose()


@pytest.fixture
def db_pagos(db_usuarios, monkeypatch, tmp_path):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    asyncio.run(preparar(db_usuarios))
    new_engine = create_async_engine(
        db_usuarios.url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": db_usuarios.esquema}},
    )
    db_usuarios.engine = new_engine
    db_usuarios.sessions = async_sessionmaker(new_engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path / "vouchers"))
    return db_usuarios


@pytest_asyncio.fixture
async def api_pagos(db_pagos):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, db_pagos
