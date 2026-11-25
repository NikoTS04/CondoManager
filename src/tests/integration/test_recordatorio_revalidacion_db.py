"""CON-33: la elegibilidad del recordatorio se revalida al despachar, bajo FOR SHARE."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from src.core.config import settings
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.models import AlertaNotificacion, IntentoNotificacion, Notificacion
from src.modules.notificaciones.recordatorios import generar_recordatorios
from src.modules.notificaciones.worker import procesar_uno
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]

AHORA = datetime(2026, 11, 21, 13, tzinfo=UTC)


async def recordatorios_en_cola(base, monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    cuota = CuotaMantenimiento(
        departamento_id=did("102"),
        periodo="2026-11",
        monto_ordinario=100,
        monto_total_exigible=100,
        fecha_emision=AHORA.date(),
        fecha_vencimiento=AHORA.date() + timedelta(days=3),
    )
    async with base.sessions() as db, db.begin():
        db.add(cuota)
    await generar_recordatorios(base.sessions, AHORA)
    async with base.sessions() as db:
        total = await db.scalar(select(func.count()).select_from(Notificacion))
    assert total > 0
    return cuota.id, total


async def assert_suprimidos_sin_transporte(base, total, motivo):
    async with base.sessions() as db:
        logs = list(await db.scalars(select(Notificacion)))
        assert len(logs) == total
        assert {(n.estado, n.error_mensaje, n.intentos) for n in logs} == {("OMITIDO", motivo, 0)}
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 0
        assert await db.scalar(select(func.count()).select_from(AlertaNotificacion)) == 0


async def test_cuota_pagada_deja_estado_terminal_explicito_sin_transporte(
    api_usuarios, monkeypatch
):
    _, base = api_usuarios
    cuota_id, total = await recordatorios_en_cola(base, monkeypatch)
    async with base.sessions() as db, db.begin():
        (await db.get(CuotaMantenimiento, cuota_id)).monto_pagado = 100
    while await procesar_uno(base.sessions, transport=lambda *a: pytest.fail("cuota pagada")):
        pass
    await assert_suprimidos_sin_transporte(base, total, "RECORDATORIO_SIN_DEUDA")


async def test_vencimiento_modificado_no_envia_el_aviso_viejo(api_usuarios, monkeypatch):
    _, base = api_usuarios
    cuota_id, total = await recordatorios_en_cola(base, monkeypatch)
    async with base.sessions() as db, db.begin():
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        cuota.fecha_vencimiento = cuota.fecha_vencimiento + timedelta(days=10)
    while await procesar_uno(base.sessions, transport=lambda *a: pytest.fail("vencimiento movido")):
        pass
    await assert_suprimidos_sin_transporte(base, total, "RECORDATORIO_SIN_DEUDA")


async def test_pago_en_curso_bloquea_al_worker_y_se_relee_el_saldo(api_usuarios, monkeypatch):
    _, base = api_usuarios
    cuota_id, _ = await recordatorios_en_cola(base, monkeypatch)
    enviados = []

    def enviar(log, clave):
        enviados.append(log.id)
        return {"status": 200, "message_id": "1"}

    pago = base.sessions()
    async with pago.begin():
        # El pago modifica la cuota y aún no confirma: el worker no puede decidir con un saldo viejo.
        (await pago.get(CuotaMantenimiento, cuota_id)).monto_pagado = 100
        await pago.flush()
        tarea = asyncio.create_task(procesar_uno(base.sessions, transport=enviar))
        await asyncio.sleep(1)
        assert not tarea.done()
    assert await asyncio.wait_for(tarea, 30)
    await pago.close()
    assert enviados == []
    async with base.sessions() as db:
        estados = {n.estado for n in await db.scalars(select(Notificacion))}
        assert "OMITIDO" in estados
