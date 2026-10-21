"""Migración aditiva: resultados/hashes antiguos intactos y evidencia versionada."""

import json
from datetime import date
from importlib import import_module
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_areas_demo import cargar_areas_demo
from scripts.seed_usuarios_demo import cargar_demo
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.models_persistencia import ArchivoVoucher, RevisionPago
from src.modules.pagos.persistencia import PagosPersistentesService
from src.modules.usuarios.demo import id_demo
from src.tests.pagos_db import did
from src.tests.usuarios_db import REVISIONES, migrar

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def test_migracion_conserva_resultado_y_asocia_evidencia(db_usuarios):
    async with db_usuarios.engine.connect() as conn, conn.begin():
        esquema = "con72_legacy_" + uuid4().hex
        await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
        await conn.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await conn.run_sync(lambda c: migrar(c, REVISIONES[:-1]))
        cid, rid, nombre = uuid4(), uuid4(), f"{uuid4()}.png"
        resultado = {
            "comprobante_id": str(cid),
            "estado_final": "OBSERVADO",
            "monto_imputado": "0.00",
            "nuevo_saldo_departamento": "170.00",
            "saldo_a_favor_generado": "0.00",
            "departamento_habilitado_reservas": False,
        }
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            await cargar_demo(db)
            await cargar_areas_demo(db)
            db.add(
                ComprobantePago(
                    id=cid,
                    departamento_id=did(),
                    banco_origen="BCP",
                    numero_operacion="0001",
                    fecha_operacion=date(2026, 10, 15),
                    monto="170.00",
                    url_voucher=nombre,
                    idempotency_hash="f" * 64,
                    estado="OBSERVADO",
                    motivo_rechazo="Motivo público",
                )
            )
            await db.flush()
            db.add(
                ArchivoVoucher(
                    nombre=nombre,
                    departamento_id=did(),
                    usuario_id=id_demo("moroso402@villabonita3.pe"),
                    content_type="image/png",
                    size_bytes=100,
                    comprobante_id=cid,
                )
            )
            await db.flush()
            await conn.execute(
                text("""INSERT INTO revisiones_pago
                (id, comprobante_id, decision, motivo, actor_id, creado_en, resultado)
                VALUES (:rid, :cid, 'OBSERVADO', 'Motivo público', :actor, now(), CAST(:resultado AS JSONB))"""),
                {
                    "rid": rid,
                    "cid": cid,
                    "actor": id_demo("admin@villabonita3.pe"),
                    "resultado": json.dumps(resultado),
                },
            )

            def upgrade(c):
                with Operations.context(MigrationContext.configure(c)):
                    import_module("migrations.versions.20261021_0013_convergencia_con72").upgrade()

            await conn.run_sync(upgrade)
            revision = await db.get(RevisionPago, rid)
            assert revision.archivo_nombre == nombre and revision.notas_internas is None
            assert revision.resultado == resultado
            assert (
                PagosPersistentesService.resultado_revision(revision).motivo_rechazo
                == "Motivo público"
            )
            pago = await db.get(ComprobantePago, cid)
            assert pago.idempotency_hash == "f" * 64 and pago.numero_operacion == "0001"
            db.add(
                ArchivoVoucher(
                    nombre=f"{uuid4()}.png",
                    departamento_id=did(),
                    usuario_id=id_demo("moroso402@villabonita3.pe"),
                    content_type="image/png",
                    size_bytes=100,
                    comprobante_id=cid,
                )
            )
            await db.flush()
            assert len(list(await db.scalars(select(ArchivoVoucher)))) == 2
            assert not any(
                u["column_names"] == ["comprobante_id"]
                for u in await conn.run_sync(
                    lambda c: inspect(c).get_unique_constraints("archivos_voucher")
                )
            )
        # El esquema y todos los datos de esta adopción se revierten al terminar.
        await conn.rollback()
