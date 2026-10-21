"""Adopción de históricos y rechazo seguro sobre esquemas PostgreSQL aislados."""

from importlib import import_module
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_areas_demo import cargar_areas_demo
from scripts.seed_usuarios_demo import cargar_demo
from src.tests.pagos_db import did
from src.tests.usuarios_db import REVISIONES, migrar

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
AREA = "11111111-1111-1111-1111-111111111101"


def upgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        import_module("migrations.versions.20261020_0012_reservas_notificaciones").upgrade()


@pytest.mark.parametrize("incompatible", [False, True])
async def test_adopta_sin_perder_instantes_o_revierte_sin_perder_datos(db_usuarios, incompatible):
    async with db_usuarios.engine.connect() as conn:
        transaccion = await conn.begin()
        try:
            esquema = "con73_legacy_" + uuid4().hex
            await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conn.run_sync(
                lambda c: migrar(
                    c, REVISIONES[: REVISIONES.index("20261020_0012_reservas_notificaciones")]
                )
            )
            async with AsyncSession(bind=conn, expire_on_commit=False) as db:
                await cargar_demo(db)
                await cargar_areas_demo(db)
                await db.commit()
            await conn.execute(
                text("""
                CREATE TABLE reservas (
                  id UUID PRIMARY KEY, area_id UUID NOT NULL REFERENCES areas_comunes(id) ON DELETE RESTRICT,
                  departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
                  fecha_reserva DATE NOT NULL, hora_inicio TIME NOT NULL, hora_fin TIME NOT NULL,
                  costo_reserva NUMERIC(12,2) NOT NULL, estado VARCHAR(20) NOT NULL,
                  creado_en TIMESTAMPTZ NOT NULL)
            """)
            )
            rid = uuid4()
            await conn.execute(
                text("""INSERT INTO reservas VALUES
                (:rid, :area, :did, '2026-10-30', '19:00', '21:00', 35.75, 'CONFIRMADA', '2026-10-20T15:00:00Z')"""),
                {"rid": rid, "area": AREA, "did": did("102")},
            )
            if incompatible:
                await conn.execute(
                    text("ALTER TABLE reservas ALTER COLUMN costo_reserva TYPE NUMERIC(10,2)")
                )
                with pytest.raises(RuntimeError, match="costo_reserva"):
                    async with conn.begin_nested():
                        await conn.run_sync(upgrade)
                assert (await conn.execute(text("SELECT id FROM reservas"))).scalar_one() == rid
                assert (
                    await conn.execute(text("SELECT to_regclass('notificaciones_logs')"))
                ).scalar_one() is None
            else:
                await conn.run_sync(upgrade)
                row = (
                    (await conn.execute(text("SELECT * FROM reservas WHERE id=:id"), {"id": rid}))
                    .mappings()
                    .one()
                )
                assert row["hora_inicio"].isoformat() == "19:00:00"
                assert row["zona_horaria"] == "UTC" and str(row["costo_reserva"]) == "35.75"
                assert row["moneda"] == "PEN" and row["usuario_id"] is None
                assert row["creado_en"].isoformat() == "2026-10-20T15:00:00+00:00"
        finally:
            await transaccion.rollback()
