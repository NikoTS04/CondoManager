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
from src.modules.reservas import router as reservas
from src.modules.usuarios.piloto import vinculo_piloto


def migrar_pagos(connection):
    with Operations.context(MigrationContext.configure(connection)):
        import_module("migrations.versions.20261020_0009_pagos_persistentes").upgrade()


def did(numero="402"):
    return UUID(vinculo_piloto(numero, "PROPIETARIO_TITULAR")["departamento_id"])


async def preparar(base):
    async with base.engine.begin() as conn:
        await conn.run_sync(migrar_pagos)
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
    asyncio.run(preparar(db_usuarios))
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path / "vouchers"))
    monkeypatch.setattr(reservas, "RESERVAS_REGISTRADAS", {})
    return db_usuarios


@pytest_asyncio.fixture
async def api_pagos(db_pagos):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, db_pagos
