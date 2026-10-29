"""Devengos, retroactivos y locks sobre PostgreSQL real; sin adoptar saldos históricos."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.consumo import consumir
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_mora import (
    AjusteDevengoMora,
    ConciliacionDiaria,
    DevengoMora,
    EventoMoraOutbox,
    MovimientoImputacionDiaria,
)
from src.modules.pagos.models_persistencia import RevisionPago
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.worker import evaluar_moras_diarias, publicar_pendientes
from src.tests.integration.test_pagos_db import imagen, login
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
HOY = date(2026, 10, 20)
AHORA = datetime(2026, 10, 20, 12, tzinfo=UTC)


@pytest_asyncio.fixture
async def diaria(api_usuarios, monkeypatch, tmp_path):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path / "vouchers"))
    monkeypatch.setattr("src.modules.pagos.persistencia.fecha_lima", lambda: HOY)
    monkeypatch.setattr("src.modules.cuotas.emision.fecha_lima", lambda: date(2026, 10, 1))
    async with base.sessions() as db, db.begin():
        c = CuotaMantenimiento(
            id=uuid4(),
            departamento_id=did(),
            periodo="2026-10",
            monto_ordinario=Decimal("100.00"),
            monto_total_exigible=Decimal("100.00"),
            monto_pagado=Decimal("0.00"),
            fecha_emision=date(2026, 10, 1),
            fecha_vencimiento=date(2026, 10, 10),
            estado="PENDIENTE",
            dias_gracia_aplicados=0,
            politica_mora_aplicada={
                "modalidad": "MONTO_DIARIO",
                "monto_diario": "1.00",
                "dias_gracia": 0,
                "zona_horaria": "America/Lima",
                "version": 1,
            },
        )
        db.add(c)
        cid = c.id
        departamento = await db.get(Departamento, did())
        departamento.saldo_a_favor = Decimal("0.00")
    return client, base, cid


async def reportar(client, headers, dia=10, monto="100.00"):
    r = await client.post(
        "/api/v1/pagos/reportar",
        headers=headers,
        data={
            "departamento_id": str(did()),
            "banco": "BCP",
            "numero_operacion": uuid4().hex,
            "fecha_operacion": date(2026, 10, dia).isoformat(),
            "monto": monto,
        },
        files={"archivo_voucher": ("voucher.png", imagen(), "image/png")},
    )
    assert r.status_code == 202, r.text
    return r.json()["comprobante_id"]


async def aprobar(client, junta, id):
    r = await client.post(
        f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_worker_recupera_no_duplica_y_usa_snapshot(diaria):
    _, base, cuota_id = diaria
    async with base.sessions() as db, db.begin():
        c = await db.get(Condominio, UUID(base.cid))
        c.dias_gracia = 30  # No altera la gracia histórica ni depende de la política actual.
    await asyncio.gather(*[evaluar_moras_diarias(base.sessions, HOY, AHORA) for _ in range(2)])
    await base.engine.dispose()
    async with base.sessions() as db:
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        assert cuota.monto_mora == Decimal("10.00") and cuota.monto_total_exigible == Decimal(
            "110.00"
        )
        assert cuota.estado == "EN_MORA"
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 10
        assert await db.scalar(select(func.count()).select_from(EventoMoraOutbox)) == 10
        logs = await db.scalar(select(func.count()).select_from(AuditoriaLogORM))
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM)) == logs


@pytest.mark.parametrize("dia,monto,mora", [(10, "100.00", "0.00"), (12, "102.00", "2.00")])
async def test_aprobacion_tardia_usa_fecha_bancaria_y_compensa(diaria, dia, monto, mora):
    client, base, cuota_id = diaria
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    id = await reportar(client, residente, dia, monto)
    recibido = await aprobar(client, junta, id)
    assert recibido["monto_imputado"] == monto and recibido["nuevo_saldo_departamento"] == "0.00"
    async with base.sessions() as db:
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        assert cuota.monto_mora == Decimal(mora) and cuota.estado == "PAGADA"
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 10
        assert await db.scalar(select(func.sum(AjusteDevengoMora.importe))) == Decimal(
            mora
        ) - Decimal("10.00")
        conteo = await db.scalar(select(func.count()).select_from(EventoMoraOutbox))
    assert await aprobar(client, junta, id) == recibido
    await evaluar_moras_diarias(base.sessions, date(2026, 11, 30), AHORA + timedelta(days=41))
    async with base.sessions() as db:
        assert (await db.get(CuotaMantenimiento, cuota_id)).monto_mora == Decimal(mora)
        assert await db.scalar(select(func.count()).select_from(EventoMoraOutbox)) == conteo


async def test_retroactivo_reordena_pagos_sin_reescribir_recibos(diaria):
    client, base, cuota_id = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    posterior = await reportar(client, residente, 12, "50.00")
    recibo = await aprobar(client, junta, posterior)
    assert recibo["nuevo_saldo_departamento"] == "60.00"
    anterior = await reportar(client, residente, 10, "100.00")
    assert (await aprobar(client, junta, anterior))["nuevo_saldo_departamento"] == "0.00"
    async with base.sessions() as db:
        c = await db.get(CuotaMantenimiento, cuota_id)
        assert c.monto_mora == 0 and c.monto_pagado == Decimal("100.00")
        assert (await db.get(Departamento, did())).saldo_a_favor == Decimal("50.00")
        assert await db.scalar(
            select(ImputacionPago.monto_aplicado).where(
                ImputacionPago.comprobante_id == UUID(posterior)
            )
        ) == Decimal("50.00")
        assert (
            await db.scalar(
                select(func.sum(MovimientoImputacionDiaria.importe)).where(
                    MovimientoImputacionDiaria.comprobante_id == UUID(posterior),
                    MovimientoImputacionDiaria.componente == "MORA",
                )
            )
            == 0
        )
        assert await db.scalar(
            select(func.sum(MovimientoImputacionDiaria.importe)).where(
                MovimientoImputacionDiaria.comprobante_id == UUID(posterior),
                MovimientoImputacionDiaria.componente == "CREDITO",
            )
        ) == Decimal("50.00")
        assert (
            await db.scalar(
                select(RevisionPago).where(RevisionPago.comprobante_id == UUID(posterior))
            )
        ).resultado == recibo
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        assert all(b.hash_previo == a.hash_actual for a, b in zip(logs, logs[1:]))
    assert await aprobar(client, junta, posterior) == recibo


async def test_pausa_24h_y_rechazo_recuperan_fechas(diaria):
    client, base, cuota_id = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    id = await reportar(client, residente)
    async with base.sessions() as db, db.begin():
        (await db.get(ComprobantePago, UUID(id))).creado_en = AHORA - timedelta(hours=2)
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    await evaluar_moras_diarias(base.sessions, HOY, AHORA + timedelta(hours=20))
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 0
        assert (await db.get(CuotaMantenimiento, cuota_id)).monto_pagado == 0
    r = await client.post(
        f"/api/v1/pagos/{id}/conciliar",
        headers=junta,
        json={"decision": "RECHAZADO", "motivo_rechazo": "Operación no acreditada"},
    )
    assert r.status_code == 200, r.text
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 10
    # Otro voucher no renueva su pausa por reintentar el cron o subsanarlo.
    otro = await reportar(client, residente)
    async with base.sessions() as db, db.begin():
        (await db.get(ComprobantePago, UUID(otro))).creado_en = AHORA - timedelta(hours=25)
    await evaluar_moras_diarias(base.sessions, date(2026, 10, 21), AHORA)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 11


async def test_fallo_auditoria_revierte_pago_devengos_y_outbox(diaria, monkeypatch):
    client, base, cuota_id = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    id = await reportar(client, residente, 12, "102.00")

    async def fallar(*_, **__):
        raise RuntimeError("Auditoría no disponible")

    monkeypatch.setattr(SQLAlchemyPagosRepository, "auditar", fallar)
    r = await client.post(
        f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
    )
    assert r.status_code == 500
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, UUID(id))).estado == "EN_REVISION"
        assert (await db.get(CuotaMantenimiento, cuota_id)).monto_mora == 0
        for modelo in (
            ConciliacionDiaria,
            DevengoMora,
            EventoMoraOutbox,
            MovimientoImputacionDiaria,
            ImputacionPago,
            RevisionPago,
        ):
            assert await db.scalar(select(func.count()).select_from(modelo)) == 0


async def test_aprobaciones_y_worker_concurrentes_no_duplican(diaria):
    client, base, cuota_id = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    a = await reportar(client, residente, 10, "100.00")
    b = await reportar(client, residente, 12, "50.00")
    await asyncio.gather(
        aprobar(client, junta, b),
        aprobar(client, junta, a),
        evaluar_moras_diarias(base.sessions, HOY, AHORA),
    )
    async with base.sessions() as db:
        c = await db.get(CuotaMantenimiento, cuota_id)
        assert c.estado == "PAGADA" and c.monto_mora == 0
        assert (await db.get(Departamento, did())).saldo_a_favor == Decimal("50.00")
        assert await db.scalar(select(func.count()).select_from(RevisionPago)) == 2


async def test_eventos_versionados_consumo_y_relay_recuperable(diaria):
    client, base, _ = diaria
    await evaluar_moras_diarias(base.sessions, date(2026, 10, 11), AHORA)
    schema = json.loads(
        Path("specs/03-contracts/events/schemas/mora-diaria.v2.schema.json").read_text()
    )
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    await aprobar(client, junta, await reportar(client, residente))
    async with base.sessions() as db:
        eventos = list(await db.scalars(select(EventoMoraOutbox)))
        assert {e.payload["event_type"] for e in eventos} == {
            "MoraAplicadaEvent",
            "MoraAjustadaEvent",
        }
    for e in eventos:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(e.payload)
        assert await consumir(base.sessions, e.payload) == 1
        assert await consumir(base.sessions, e.payload) == 0

    class Redis:
        mensajes = []
        fallar = False

        async def xadd(self, _, mensaje):
            self.mensajes.append(mensaje)
            if self.fallar and json.loads(mensaje["event"])["event_type"].startswith("Mora"):
                raise ConnectionError("Respuesta perdida")

    redis = Redis()
    redis.fallar = True
    with pytest.raises(ConnectionError):
        await publicar_pendientes(redis, base.sessions)
    primero = redis.mensajes[-1]
    redis.fallar = False
    await publicar_pendientes(redis, base.sessions)
    assert redis.mensajes[-len(eventos)] == primero


async def test_ledger_inmutable_y_downgrade_protegido(diaria):
    _, base, _ = diaria
    await evaluar_moras_diarias(base.sessions, date(2026, 10, 11), AHORA)
    async with base.sessions() as db:
        with pytest.raises(DBAPIError, match="inmutable"):
            await db.execute(text("UPDATE devengos_mora SET importe=2"))
        await db.rollback()

    def downgrade(conn):
        with Operations.context(MigrationContext.configure(conn)):
            import_module("migrations.versions.20261025_0019_motor_mora_diaria").downgrade()

    with pytest.raises(DBAPIError, match="operaciones diarias"):
        async with base.engine.begin() as conn:
            await conn.run_sync(downgrade)


async def test_fecha_bancaria_futura_no_se_aprueba(diaria):
    client, base, _ = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    id = await reportar(client, residente, 21)
    r = await client.post(
        f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
    )
    assert r.status_code == 422 and r.json()["error_code"] == "FECHA_BANCARIA_FUTURA"
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, UUID(id))).estado == "EN_REVISION"
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 0


async def test_nuevo_reporte_no_prolonga_pausa_del_pendiente_antiguo(diaria):
    client, base, _ = diaria
    residente = await login(client)
    viejo = await reportar(client, residente)
    fresco = await reportar(client, residente)
    async with base.sessions() as db, db.begin():
        (await db.get(ComprobantePago, UUID(viejo))).creado_en = AHORA - timedelta(hours=25)
        (await db.get(ComprobantePago, UUID(fresco))).creado_en = AHORA - timedelta(hours=1)
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(DevengoMora)) == 10


async def test_credito_consumido_no_se_reutiliza_en_otra_cuota_del_mismo_dia(diaria):
    client, base, _ = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    await aprobar(client, junta, await reportar(client, residente, 20, "200.00"))
    async with base.sessions() as db, db.begin():
        d = await db.get(Departamento, did())
        assert d.saldo_a_favor == Decimal("90.00")
        # Base fija de CON-13: cuota emitida después de la aprobación, el mismo día bancario.
        d.saldo_a_favor = Decimal("0.00")
        nueva = CuotaMantenimiento(
            id=uuid4(),
            departamento_id=did(),
            periodo="2026-09",
            monto_ordinario=Decimal("100.00"),
            monto_total_exigible=Decimal("100.00"),
            monto_pagado=Decimal("90.00"),
            fecha_emision=HOY,
            fecha_vencimiento=date(2026, 9, 10),
            estado="PENDIENTE",
            dias_gracia_aplicados=0,
            politica_mora_aplicada={
                "modalidad": "MONTO_DIARIO",
                "monto_diario": "1.00",
                "dias_gracia": 0,
                "zona_horaria": "America/Lima",
                "version": 1,
            },
        )
        db.add(nueva)
        id = nueva.id
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    async with base.sessions() as db:
        assert (await db.get(CuotaMantenimiento, id)).monto_pagado == Decimal("90.00")
        assert (await db.get(Departamento, did())).saldo_a_favor == 0
        assert await db.scalar(select(func.count()).select_from(ConciliacionDiaria)) == 1


async def test_deficit_por_credito_utilizado_rechaza_sin_mutar(diaria):
    client, base, cuota_id = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    await aprobar(client, junta, await reportar(client, residente, 10, "200.00"))
    async with base.sessions() as db, db.begin():
        # Simula una rectificación de principal y consumo de crédito por otro proceso.
        d = await db.get(Departamento, did())
        d.saldo_a_favor = Decimal("0.00")
        c = await db.get(CuotaMantenimiento, cuota_id)
        c.monto_ordinario = c.monto_total_exigible = Decimal("110.00")
    id = await reportar(client, residente, 20, "1.00")
    r = await client.post(
        f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
    )
    assert r.status_code == 409 and r.json()["error_code"] == "CREDITO_RETROACTIVO_CONSUMIDO"
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, UUID(id))).estado == "EN_REVISION"
        assert (await db.get(Departamento, did())).saldo_a_favor == 0
        assert (await db.get(CuotaMantenimiento, cuota_id)).monto_pagado == Decimal("100.00")
        assert await db.scalar(select(func.count()).select_from(ConciliacionDiaria)) == 1


async def test_nuevas_emisiones_diarias_operativas_y_credito_de_emision(monkeypatch):
    from src.tests.integration.test_emision_db import base_emision, emitir, preparar

    monkeypatch.setattr("src.modules.cuotas.emision.fecha_lima", lambda: date(2026, 10, 1))
    async with base_emision() as factory:
        cid = await preparar(factory)
        async with factory() as db, db.begin():
            c = await db.get(Condominio, cid)
            c.regla_mora_tipo, c.monto_mora_fijo = "MONTO_DIARIO", None
            c.monto_mora_diario, c.dias_gracia = Decimal("1.00"), 0
        assert (await emitir(factory, cid)).total_cuotas_emitidas == 3
        await evaluar_moras_diarias(factory, date(2026, 10, 23), AHORA)
        async with factory() as db:
            cuotas = list(
                await db.scalars(
                    select(CuotaMantenimiento).order_by(CuotaMantenimiento.departamento_id)
                )
            )
            assert all(c.politica_mora_aplicada["modalidad"] == "MONTO_DIARIO" for c in cuotas)
            assert cuotas[0].estado == "PAGADA" and cuotas[0].monto_mora == 0
            assert sum(c.monto_mora for c in cuotas) == Decimal("6.00")
