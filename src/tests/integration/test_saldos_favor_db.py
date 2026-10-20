"""Integración PostgreSQL optativa: CON13_TEST_DATABASE_URL (base de pruebas).

Cada prueba crea un esquema aleatorio dentro de una transacción que se revierte;
no usa la base configurada por la aplicación ni modifica tablas existentes.
"""

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.core.database import Base
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor
from src.modules.cuotas.saldos.repository import SQLAlchemySaldoFavorRepository
from src.modules.cuotas.saldos.service import ActorSaldoFavor, SaldosFavorService


@pytest_asyncio.fixture
async def session_saldos():
    url = os.environ.get("CON13_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina CON13_TEST_DATABASE_URL para validar PostgreSQL real.")
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            esquema = f"con13_{uuid4().hex}"
            await connection.execute(text(f'CREATE SCHEMA "{esquema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            tablas = [
                modelo.__table__
                for modelo in (
                    Condominio,
                    Edificio,
                    Departamento,
                    CuotaMantenimiento,
                    AplicacionSaldoFavor,
                    AuditoriaLogORM,
                )
            ]
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=tablas))
            async with AsyncSession(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            ) as session:
                yield session
        finally:
            await transaction.rollback()
    await engine.dispose()


async def crear_cuota(session):
    condominio = Condominio(
        id=uuid4(),
        nombre="Prueba CON-13",
        direccion="Prueba",
        moneda="PEN",
        regla_mora_tipo="MONTO_FIJO",
        monto_mora_fijo=Decimal("0.00"),
        dia_vencimiento=20,
        dias_gracia=2,
    )
    edificio = Edificio(
        id=uuid4(), condominio_id=condominio.id, nombre_bloque="Torre", total_pisos=1
    )
    departamento = Departamento(
        id=uuid4(),
        edificio=edificio,
        numero="101",
        piso=1,
        coeficiente_participacion=Decimal("100.0000"),
        saldo_a_favor=Decimal("200.00"),
    )
    cuota = CuotaMantenimiento(
        id=uuid4(),
        departamento_id=departamento.id,
        periodo="2026-10",
        monto_ordinario=Decimal("150.00"),
        monto_total_exigible=Decimal("150.00"),
        monto_pagado=Decimal("0.00"),
        monto_descuento=Decimal("0.00"),
        estado="EMITIDA",
        fecha_emision=date(2026, 10, 1),
        fecha_vencimiento=date(2026, 10, 20),
    )
    # Sin relationship entre cuota y departamento, el flush no garantiza el orden de INSERT.
    session.add_all([condominio, edificio, departamento])
    await session.flush()
    session.add(cuota)
    await session.flush()
    return cuota, departamento


@pytest.mark.asyncio
async def test_persistencia_checks_e_idempotencia(session_saldos):
    session = session_saldos
    cuota, departamento = await crear_cuota(session)
    actor = ActorSaldoFavor(
        "CON11_WORKER", "SISTEMA_AUTOMATICO", departamento.edificio.condominio_id
    )
    service = SaldosFavorService(SQLAlchemySaldoFavorRepository(session))
    aplicacion = await service.aplicar_a_cuota_emitida(cuota, actor)
    assert (await service.aplicar_a_cuota_emitida(cuota, actor)).id == aplicacion.id
    await session.refresh(cuota)
    await session.refresh(departamento)
    assert cuota.monto_total_exigible == cuota.monto_pagado == Decimal("150.00")
    assert cuota.estado == "PAGADA" and cuota.monto_pendiente == 0
    assert departamento.saldo_a_favor == Decimal("50.00")
    for modelo in (AplicacionSaldoFavor, AuditoriaLogORM):
        assert await session.scalar(select(func.count()).select_from(modelo)) == 1


@pytest.mark.asyncio
async def test_fallo_sql_revierte_todas_las_escrituras(session_saldos):
    session = session_saldos
    cuota, departamento = await crear_cuota(session)

    class RepositoryConFallo(SQLAlchemySaldoFavorRepository):
        async def guardar(self, cuota, departamento, aplicacion, auditoria):
            await super().guardar(cuota, departamento, aplicacion, auditoria)
            raise RuntimeError("Fallo después del flush")

    actor = ActorSaldoFavor(
        "CON11_WORKER", "SISTEMA_AUTOMATICO", departamento.edificio.condominio_id
    )
    with pytest.raises(RuntimeError):
        await SaldosFavorService(RepositoryConFallo(session)).aplicar_a_cuota_emitida(cuota, actor)
    await session.refresh(cuota)
    await session.refresh(departamento)
    assert cuota.estado == "EMITIDA" and cuota.monto_pagado == 0
    assert departamento.saldo_a_favor == Decimal("200.00")
    for modelo in (AplicacionSaldoFavor, AuditoriaLogORM):
        assert await session.scalar(select(func.count()).select_from(modelo)) == 0
