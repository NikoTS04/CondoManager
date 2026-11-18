"""CON-33: recordatorios de vencimiento sobre PostgreSQL real.

Reloj financiero fijo (hoy = 20/10/2026 en Lima, ver `pagos_sprint3`). El proveedor se
sustituye por un callable; ninguna prueba sale a la red.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core.config import settings
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.models import IntentoNotificacion, Notificacion
from src.modules.notificaciones.recordatorios import (
    TIPO_RECORDATORIO,
    ProgramadorDiario,
    operacion_recordatorio,
    programar_recordatorios,
)
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.notificaciones.worker import procesar_uno
from src.tests.pagos_db import did
from src.tests.pagos_sprint3 import reportar, revisar
from src.tests.pagos_sprint3 import sistema as sistema

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]

# 08:00 en Lima del 20/10/2026; la cuota de prueba vence en 3 días.
AHORA = datetime(2026, 10, 20, 13, tzinfo=UTC)
EN_TRES_DIAS = {"vencimiento": date(2026, 10, 23)}


@pytest.fixture
def smtp_activo(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_TRANSPORTE", "SMTP")


def proveedor_ok():
    enviados = []

    def enviar(log, clave):
        enviados.append(log)
        return {"status": 200, "message_id": f"<{clave}@prueba>"}

    enviar.enviados = enviados
    return enviar


def proveedor_prohibido(*_):
    pytest.fail("un recordatorio suprimido no debe llegar al transporte")


async def recordatorios(base):
    async with base.sessions() as db:
        return list(
            await db.scalars(
                select(Notificacion)
                .where(Notificacion.tipo_evento == TIPO_RECORDATORIO)
                .order_by(Notificacion.usuario_destinatario_id)
            )
        )


async def destinatarios_102(base):
    async with base.sessions() as db:
        filas = await NotificacionesRepository(db).destinatarios(base.cid, did("102"), "EMAIL")
        return {u.id for u, _, _ in filas}


async def intentos(base):
    async with base.sessions() as db:
        return list(await db.scalars(select(IntentoNotificacion)))


async def despachar_todo(base, proveedor, ahora=AHORA):
    while await procesar_uno(base.sessions, ahora=ahora, proveedor=proveedor):
        pass


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_programa_un_recordatorio_por_destinatario_y_es_idempotente(sistema):
    _, base, cuota_id, _, _ = sistema
    esperados = await destinatarios_102(base)
    assert esperados
    assert await programar_recordatorios(base.sessions, AHORA) == len(esperados)
    # Reinicio del worker o segunda pasada del día: ningún mensaje lógico nuevo.
    assert await programar_recordatorios(base.sessions, AHORA) == 0
    assert await programar_recordatorios(base.sessions, AHORA + timedelta(days=1)) == 0
    filas = await recordatorios(base)
    assert {f.usuario_destinatario_id for f in filas} == esperados
    assert len(filas) == len(esperados)
    operacion = operacion_recordatorio(cuota_id, date(2026, 10, 23))
    for fila in filas:
        assert (fila.evento_id, fila.operacion_id) == (cuota_id, operacion)
        assert (fila.canal, fila.finalidad, fila.estado) == ("EMAIL", "OPERATIVA", "EN_COLA")
        assert "23/10/2026" in fila.cuerpo and "S/ 100.00" in fila.cuerpo


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_dos_workers_concurrentes_no_duplican(sistema):
    _, base, _, _, _ = sistema
    esperados = await destinatarios_102(base)
    creados = await asyncio.gather(
        programar_recordatorios(base.sessions, AHORA),
        programar_recordatorios(base.sessions, AHORA),
    )
    assert sum(creados) == len(esperados)
    assert len(await recordatorios(base)) == len(esperados)


@pytest.mark.parametrize(
    ("vencimiento", "esperado"),
    [
        (date(2026, 10, 10), False),  # vencida: nunca se envía en bloque una fecha pasada
        (date(2026, 10, 19), False),
        (date(2026, 10, 20), True),  # vence hoy: aún oportuno
        (date(2026, 10, 21), True),  # recuperación de un día perdido dentro de la ventana
        (date(2026, 10, 23), True),
        (date(2026, 10, 24), False),  # fuera de la anticipación configurada
    ],
)
async def test_ventana_de_anticipacion_en_calendario_de_lima(sistema, vencimiento, esperado):
    _, base, cuota_id, _, _ = sistema
    async with base.sessions() as db, db.begin():
        (await db.get(CuotaMantenimiento, cuota_id)).fecha_vencimiento = vencimiento
    assert bool(await programar_recordatorios(base.sessions, AHORA)) is esperado


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_cuota_pagada_no_se_programa(sistema):
    _, base, cuota_id, _, _ = sistema
    async with base.sessions() as db, db.begin():
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        cuota.monto_pagado, cuota.estado = cuota.monto_total_exigible, "PAGADA"
    assert await programar_recordatorios(base.sessions, AHORA) == 0


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_pago_aprobado_antes_del_despacho_suprime_sin_enviar(sistema, smtp_activo):
    client, base, _, residente, junta = sistema
    assert await programar_recordatorios(base.sessions, AHORA)
    pid = await reportar(client, residente, "100.00")
    aprobado = await revisar(client, junta, pid)
    assert aprobado.status_code == 200, aprobado.text
    assert aprobado.json()["nuevo_saldo_departamento"] == "0.00"
    await despachar_todo(base, proveedor_prohibido)
    filas = await recordatorios(base)
    assert filas and all(
        (f.estado, f.error_mensaje, f.intentos) == ("SUPRIMIDO", "SUPRIMIDO_CUOTA_PAGADA", 0)
        for f in filas
    )
    assert await intentos(base) == []


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_voucher_en_revision_no_cuenta_como_pagado(sistema, smtp_activo):
    client, base, _, residente, _ = sistema
    assert await programar_recordatorios(base.sessions, AHORA)
    await reportar(client, residente, "100.00")
    enviar = proveedor_ok()
    await despachar_todo(base, enviar)
    filas = await recordatorios(base)
    assert filas and all(f.estado == "ENVIADO" for f in filas)
    assert len(enviar.enviados) == len(filas)
    assert all("S/ 100.00" in log.cuerpo for log in enviar.enviados)


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_abono_parcial_actualiza_el_saldo_anunciado(sistema, smtp_activo):
    client, base, _, residente, junta = sistema
    assert await programar_recordatorios(base.sessions, AHORA)
    parcial = await revisar(client, junta, await reportar(client, residente, "40.00"))
    assert parcial.status_code == 200, parcial.text
    enviar = proveedor_ok()
    await despachar_todo(base, enviar)
    assert enviar.enviados
    assert all("S/ 60.00" in log.cuerpo for log in enviar.enviados)
    assert all("S/ 60.00" in f.cuerpo for f in await recordatorios(base))


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_pago_concurrente_bajo_bloqueo_decide_la_elegibilidad(sistema, smtp_activo):
    """El worker espera a la transacción que bloquea la cuota y respeta su resultado."""
    _, base, cuota_id, _, _ = sistema
    assert await programar_recordatorios(base.sessions, AHORA)
    async with base.sessions() as pago:
        await pago.begin()
        cuota = await pago.scalar(
            select(CuotaMantenimiento).where(CuotaMantenimiento.id == cuota_id).with_for_update()
        )
        tarea = asyncio.create_task(
            procesar_uno(base.sessions, ahora=AHORA, proveedor=proveedor_prohibido)
        )
        await asyncio.sleep(0.5)
        assert not tarea.done(), "el despacho no debe decidir mientras el pago está en curso"
        cuota.monto_pagado, cuota.estado = cuota.monto_total_exigible, "PAGADA"
        await pago.commit()
    assert await tarea
    suprimidos = [f for f in await recordatorios(base) if f.estado == "SUPRIMIDO"]
    assert len(suprimidos) == 1 and suprimidos[0].error_mensaje == "SUPRIMIDO_CUOTA_PAGADA"


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_despacho_tardio_tras_el_vencimiento_se_suprime(sistema, smtp_activo):
    _, base, _, _, _ = sistema
    assert await programar_recordatorios(base.sessions, AHORA)
    # Worker caído hasta después del vencimiento: no anunciar un plazo que ya pasó.
    await despachar_todo(base, proveedor_prohibido, ahora=AHORA + timedelta(days=4))
    assert all(
        (f.estado, f.error_mensaje) == ("SUPRIMIDO", "SUPRIMIDO_VENCIMIENTO_PASADO")
        for f in await recordatorios(base)
    )


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_cambio_de_vencimiento_suprime_el_anterior_y_programa_otro(sistema, smtp_activo):
    _, base, cuota_id, _, _ = sistema
    n = await programar_recordatorios(base.sessions, AHORA)
    async with base.sessions() as db, db.begin():
        (await db.get(CuotaMantenimiento, cuota_id)).fecha_vencimiento = date(2026, 10, 22)
    await despachar_todo(base, proveedor_prohibido)
    assert {f.error_mensaje for f in await recordatorios(base)} == {
        "SUPRIMIDO_VENCIMIENTO_MODIFICADO"
    }
    assert await programar_recordatorios(base.sessions, AHORA) == n
    enviar = proveedor_ok()
    await despachar_todo(base, enviar)
    assert len(enviar.enviados) == n and all("22/10/2026" in e.cuerpo for e in enviar.enviados)


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_programador_diario_respeta_hora_de_lima_y_un_pase_por_dia(sistema, monkeypatch):
    _, base, _, _, _ = sistema
    monkeypatch.setattr(settings, "RECORDATORIO_HORA_LIMA", 8)
    programador = ProgramadorDiario(base.sessions)
    # 07:59 en Lima (12:59 UTC): todavía no.
    assert await programador.tick(datetime(2026, 10, 20, 12, 59, tzinfo=UTC)) is None
    assert await programador.tick(AHORA) == len(await destinatarios_102(base))
    assert await programador.tick(AHORA + timedelta(hours=5)) is None
    # 22:00 del 20/10 en Lima es 03:00 UTC del 21/10: sigue siendo el mismo día local.
    assert await programador.tick(datetime(2026, 10, 21, 3, tzinfo=UTC)) is None
    # Un reinicio pierde el estado en memoria, pero SQL impide duplicar.
    assert await ProgramadorDiario(base.sessions).tick(AHORA) == 0
    monkeypatch.setattr(settings, "RECORDATORIOS_ACTIVOS", False)
    assert await ProgramadorDiario(base.sessions).tick(AHORA) is None


@pytest.mark.parametrize("sistema", [EN_TRES_DIAS], indirect=True)
async def test_gracia_aplicada_define_el_ultimo_dia_sin_mora(sistema):
    _, base, cuota_id, _, _ = sistema
    async with base.sessions() as db, db.begin():
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        cuota.dias_gracia_aplicados = 5
        cuota.monto_pagado = Decimal("0.00")
    assert await programar_recordatorios(base.sessions, AHORA)
    assert all("28/10/2026" in f.cuerpo for f in await recordatorios(base))
