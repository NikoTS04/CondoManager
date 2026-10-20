"""CON-11 sobre migraciones reales, sesiones independientes y PostgreSQL aislado."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.core.security import create_access_token
from src.main import app
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox, LoteCuotas
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor
from src.modules.cuotas.saldos.service import ActorSaldoFavor, SaldosFavorService
from src.modules.cuotas.schemas import EmitirLoteRequest
from src.modules.cuotas.worker import emitir_pendientes, publicar_pendientes

REVISIONES = (
    "20261008_0001_crear_condominios_y_auditoria",
    "20261008_0002_crear_presupuestos_mensuales",
    "20261014_0003_crear_configuracion_distribucion",
    "20261014_0004_crear_aplicaciones_saldo_favor",
    "20261018_0005_estructura_inmobiliaria",
    "20261019_0006_emision_cuotas",
)


def migrar(conn):
    with Operations.context(MigrationContext.configure(conn)):
        for revision in REVISIONES:
            import_module(f"migrations.versions.{revision}").upgrade()


@asynccontextmanager
async def base_emision():
    url = os.getenv("CON11_TEST_DATABASE_URL") or os.getenv("CON13_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Defina CON11_TEST_DATABASE_URL o CON13_TEST_DATABASE_URL (PostgreSQL de pruebas)."
        )
    esquema = f"con11_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": esquema}})
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conn.run_sync(migrar)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def factory():
    async with base_emision() as factory:
        yield factory


async def preparar(factory, *, metodo="EQUITATIVA", estado="APROBADO", total="100.00"):
    cid = uuid4()
    async with factory() as session, session.begin():
        session.add(
            Condominio(
                id=cid,
                nombre="CON-11",
                direccion="Prueba",
                moneda="PEN",
                regla_mora_tipo="MONTO_FIJO",
                monto_mora_fijo=Decimal("0.00"),
                dia_vencimiento=20,
                dias_gracia=2,
            )
        )
        await session.flush()
        eid = uuid4()
        session.add(Edificio(id=eid, condominio_id=cid, nombre_bloque="Norte", total_pisos=1))
        await session.flush()
        # UUIDs reproducibles para verificar el desempate del centavo residual.
        ids = [UUID(int=i) for i in range(1, 5)]
        for i, id in enumerate(ids):
            session.add(
                Departamento(
                    id=id,
                    edificio_id=eid,
                    numero=str(i + 1),
                    piso=1,
                    coeficiente_participacion=Decimal("33.3334" if i == 0 else "33.3333"),
                    saldo_a_favor=Decimal("40.00" if i == 0 else "0.00"),
                    activo=i < 3,
                )
            )
        session.add(
            PresupuestoMensual(
                id=uuid4(),
                condominio_id=cid,
                periodo="2026-10",
                moneda="PEN",
                monto_total=Decimal(total),
                fecha_vencimiento=date(2026, 10, 20),
                estado=estado,
                creado_por="prueba",
                aprobado_por="prueba" if estado == "APROBADO" else None,
                aprobado_en=None if estado != "APROBADO" else datetime.now(UTC),
            )
        )
        session.add(
            ConfiguracionDistribucion(
                id=uuid4(),
                condominio_id=cid,
                metodo=metodo,
                actualizado_por="prueba",
                actualizado_en=datetime.now(UTC),
            )
        )
    return cid


async def emitir(factory, cid, rol="ADMIN_JUNTA", contexto=None):
    async with factory() as session:
        return await EmisionCuotasService(session).emitir(
            EmitirLoteRequest(condominio_id=cid, periodo="2026-10"),
            ActorSaldoFavor("prueba", rol, contexto or cid),
        )


async def verificar_lote(factory, cid):
    async with factory() as session:
        cuotas = list(
            (
                await session.scalars(
                    select(CuotaMantenimiento).order_by(CuotaMantenimiento.departamento_id)
                )
            ).all()
        )
        assert len(cuotas) == 3
        assert sum(c.monto_ordinario for c in cuotas) == Decimal("100.00")
        assert cuotas[0].estado == "PAGADA" and cuotas[0].monto_pagado == Decimal("33.34")
        assert (await session.get(Departamento, UUID(int=1))).saldo_a_favor == Decimal("6.66")
        assert await session.scalar(select(func.count()).select_from(EventoLoteOutbox)) == 1
        assert await session.scalar(select(func.count()).select_from(AplicacionSaldoFavor)) == 3
        logs = list(
            (
                await session.scalars(
                    select(AuditoriaLogORM)
                    .where(AuditoriaLogORM.condominio_id == cid)
                    .order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
                )
            ).all()
        )
        assert len(logs) == 4
        assert logs[0].hash_previo is None
        for anterior, posterior in zip(logs, logs[1:]):
            assert posterior.hash_previo == anterior.hash_actual
        assert logs[-1].accion_ejecutada == "LOTE_CUOTAS_EMITIDO"


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo", ["EQUITATIVA", "POR_ALICUOTA"])
async def test_lote_real_creditos_cadena_y_reintento(factory, metodo):
    cid = await preparar(factory, metodo=metodo)
    response = await emitir(factory, cid)
    assert response.total_cuotas_emitidas == 3 and response.cuotas_cubiertas_saldo_favor == 1
    await verificar_lote(factory, cid)
    with pytest.raises(APIError, match="persistido"):
        await emitir(factory, cid)
    await verificar_lote(factory, cid)


@pytest.mark.asyncio
async def test_concurrencia_api_worker_un_solo_lote(factory):
    cid = await preparar(factory)
    resultados = await asyncio.gather(
        emitir(factory, cid), emitir(factory, cid, "SISTEMA_AUTOMATICO"), return_exceptions=True
    )
    assert (
        sum(isinstance(r, APIError) and r.error_code == "LOTE_YA_EMITIDO" for r in resultados) == 1
    )
    assert sum(not isinstance(r, Exception) for r in resultados) == 1
    await verificar_lote(factory, cid)


@pytest.mark.asyncio
async def test_fallo_intermedio_revierte_todo(factory, monkeypatch):
    cid = await preparar(factory)
    original = SaldosFavorService.aplicar_a_cuota_emitida

    async def fallar(self, cuota, actor):
        await original(self, cuota, actor)
        raise RuntimeError("Fallo después de aplicar crédito")

    monkeypatch.setattr(SaldosFavorService, "aplicar_a_cuota_emitida", fallar)
    with pytest.raises(RuntimeError):
        await emitir(factory, cid)
    async with factory() as session:
        for model in (
            CuotaMantenimiento,
            AplicacionSaldoFavor,
            AuditoriaLogORM,
            LoteCuotas,
            EventoLoteOutbox,
        ):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
        assert (await session.get(Departamento, UUID(int=1))).saldo_a_favor == Decimal("40.00")


@pytest.mark.asyncio
async def test_borrador_y_contexto_no_escriben(factory):
    cid = await preparar(factory, estado="BORRADOR")
    for rol, contexto, codigo in [
        ("ADMIN_JUNTA", cid, "PRESUPUESTO_NO_APROBADO"),
        ("ADMIN_JUNTA", uuid4(), "EMISION_ACCESO_DENEGADO"),
        ("AUDITOR", cid, "EMISION_ACCESO_DENEGADO"),
    ]:
        with pytest.raises(APIError) as error:
            await emitir(factory, cid, rol, contexto)
        assert error.value.error_code == codigo
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(CuotaMantenimiento)) == 0


@pytest.mark.asyncio
async def test_worker_recupera_y_relay_reintenta_sin_perder_evento(factory):
    cid = await preparar(factory)
    await emitir_pendientes(factory, date(2026, 10, 19))
    await emitir_pendientes(factory, date(2026, 10, 20))
    await verificar_lote(factory, cid)
    redis = AsyncMock()
    redis.xadd.side_effect = ConnectionError("Redis no disponible")
    with pytest.raises(ConnectionError):
        await publicar_pendientes(redis, factory)
    async with factory() as session:
        evento = await session.scalar(select(EventoLoteOutbox))
        assert evento.publicado_en is None
        event_id = str(evento.id)
    redis.xadd.side_effect = None
    await publicar_pendientes(redis, factory)
    await publicar_pendientes(redis, factory)
    assert redis.xadd.call_count == 2
    assert event_id in redis.xadd.call_args.args[1]["event"]


@pytest.mark.asyncio
async def test_http_identidad_contexto_contrato_y_persistencia(factory):
    cid = await preparar(factory)

    async def db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ruta = "/api/v1/cuotas/emitir-lote"
            body = {"condominio_id": str(cid), "periodo": "2026-10"}
            assert (await client.post(ruta, json=body)).status_code == 401
            for rol, contexto in [
                ("AUDITOR", cid),
                ("SISTEMA_AUTOMATICO", cid),
                ("ADMIN_JUNTA", uuid4()),
            ]:
                token = create_access_token(
                    {"sub": "test", "rol": rol, "condominio_id": str(contexto)}
                )
                response = await client.post(
                    ruta, json=body, headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == 403
            token = create_access_token(
                {"sub": "test", "rol": "ADMIN_JUNTA", "condominio_id": str(cid)}
            )
            headers = {"Authorization": f"Bearer {token}"}
            invalida = await client.post(
                ruta, json={**body, "presupuesto_total": "1.00"}, headers=headers
            )
            assert invalida.status_code == 422
            assert invalida.json()["error_code"] == "DATOS_EMISION_INVALIDOS"
            assert isinstance(invalida.json()["detalles"], dict)
            response = await client.post(ruta, json=body, headers=headers)
            assert response.status_code == 201, response.text
            assert response.json()["monto_total_facturado"] == "100.00"
            assert (await client.post(ruta, json=body, headers=headers)).status_code == 409
        await verificar_lote(factory, cid)
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_migracion_reversible_y_fk_con13(factory):
    async with factory() as session, session.begin():
        conn = await session.connection()

        def ciclo(conn):
            revision = import_module(f"migrations.versions.{REVISIONES[-1]}")
            with Operations.context(MigrationContext.configure(conn)):
                fks = inspect(conn).get_foreign_keys("aplicaciones_saldo_favor")
                assert any(fk["name"] == "fk_aplicacion_saldo_cuota" for fk in fks)
                revision.downgrade()
                assert "cuotas_mantenimiento" not in inspect(conn).get_table_names()
                revision.upgrade()

        await conn.run_sync(ciclo)
