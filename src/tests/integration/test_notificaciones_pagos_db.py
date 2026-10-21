"""CON-34: avisos de pagos construidos con la revisión persistida, en PostgreSQL."""

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select

from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import EventoConsumido, IncidenciaEvento, Notificacion
from src.modules.notificaciones.worker import recuperar_eventos
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.models_persistencia import EventoPagoOutbox, RevisionPago
from src.modules.usuarios.demo import id_demo
from src.tests.integration.test_convergencia_con72 import revisar
from src.tests.integration.test_pagos_db import did, login, reportar

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
RESIDENTE = id_demo("moroso402@villabonita3.pe")


async def reportar_id(client, usuario, operacion, monto):
    respuesta = await reportar(client, usuario, operacion=operacion, monto=monto)
    assert respuesta.status_code == 202, respuesta.text
    return respuesta.json()["comprobante_id"]


async def recorrido(client):
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    aprobado = await reportar_id(client, usuario, "OP-APROBADO", "100.00")
    observado = await reportar_id(client, usuario, "OP-OBSERVADO", "50.00")
    rechazado = await reportar_id(client, usuario, "OP-RECHAZADO", "30.00")
    respuesta = await revisar(client, junta, aprobado, "APROBADO", None)
    assert respuesta.status_code == 200, respuesta.text
    respuesta = await revisar(client, junta, observado, "OBSERVADO", "Imagen ilegible")
    assert respuesta.status_code == 200, respuesta.text
    respuesta = await revisar(client, junta, rechazado, "RECHAZADO", "Operación no figura")
    assert respuesta.status_code == 200, respuesta.text
    return aprobado, observado, rechazado


def por_comprobante(logs):
    return {(str(log.operacion_id), log.tipo_evento): log for log in logs}


async def test_avisos_de_pago_usan_revision_persistida_y_no_duplican(api_pagos):
    client, base = api_pagos
    aprobado, observado, rechazado = await recorrido(client)
    async with base.sessions() as db:
        eventos = list(await db.scalars(select(EventoPagoOutbox).order_by(EventoPagoOutbox.id)))
    assert len(eventos) == 6

    for evento in eventos:
        assert await consumir(base.sessions, evento.payload) == 1
        assert await consumir(base.sessions, evento.payload) == 0
    await recuperar_eventos(base.sessions)
    await base.engine.dispose()

    async with base.sessions() as db:
        logs = list(await db.scalars(select(Notificacion)))
        revisiones = {str(r.comprobante_id): r for r in await db.scalars(select(RevisionPago))}
        comprobantes = {str(c.id): c for c in await db.scalars(select(ComprobantePago))}
        cuotas = list(await db.scalars(select(CuotaMantenimiento)))
        assert await db.scalar(select(func.count()).select_from(EventoConsumido)) == 6
        assert await db.scalar(select(func.count()).select_from(IncidenciaEvento)) == 0
    assert len(logs) == 6
    indice = por_comprobante(logs)
    ids_evento = {
        (e.payload["data"]["comprobante_id"], e.payload["event_type"]): e for e in eventos
    }

    for log in logs:
        assert log.departamento_id == did("402") and log.usuario_destinatario_id == RESIDENTE
        assert log.canal == "EMAIL" and log.destinatario == "moroso402@villabonita3.pe"
        assert log.estado == "EN_COLA" and log.intentos == 0
        assert "Dpto. 402" in log.cuerpo and "{" not in log.cuerpo

    # Recepción confirmada: monto, banco y operación del comprobante persistido.
    for id, operacion, monto in (
        (aprobado, "OP-APROBADO", "100.00"),
        (observado, "OP-OBSERVADO", "50.00"),
        (rechazado, "OP-RECHAZADO", "30.00"),
    ):
        log = indice[(id, "NOTIF_PAGO_RECIBIDO")]
        assert comprobantes[id].numero_operacion == operacion
        assert f"S/ {monto}" in log.cuerpo and "BCP" in log.cuerpo and operacion in log.cuerpo
        assert log.evento_id == UUID(ids_evento[(id, "PagoReportadoEvent")].payload["event_id"])

    # Aprobado: importes idénticos a la revisión guardada y al saldo real de las cuotas.
    log = indice[(aprobado, "NOTIF_PAGO_CONCILIADO")]
    resultado = revisiones[aprobado].resultado
    imputado = f"{Decimal(resultado['monto_imputado']):.2f}"
    saldo = f"{Decimal(resultado['nuevo_saldo_departamento']):.2f}"
    assert imputado == "100.00" and saldo == "70.00"
    assert f"Monto abonado: S/ {imputado}" in log.cuerpo
    assert f"Saldo restante del departamento: S/ {saldo}" in log.cuerpo
    assert sum((c.monto_total_exigible - c.monto_pagado for c in cuotas), Decimal(0)) == Decimal(
        saldo
    )
    assert log.evento_id == UUID(ids_evento[(aprobado, "PagoConciliadoEvent")].payload["event_id"])

    # Observado y rechazado: motivo persistido e instrucciones; sin importes aplicados.
    log = indice[(observado, "NOTIF_PAGO_OBSERVADO")]
    assert revisiones[observado].motivo == "Imagen ilegible"
    assert "Imagen ilegible" in log.cuerpo and "Subsanar voucher" in log.cuerpo
    assert "No se han aplicado saldos" in log.cuerpo and "Saldo restante" not in log.cuerpo
    log = indice[(rechazado, "NOTIF_PAGO_RECHAZADO")]
    assert revisiones[rechazado].motivo == "Operación no figura"
    assert "Operación no figura" in log.cuerpo and "no vuelva a reportar" in log.cuerpo
    for id in (observado, rechazado):
        tipo = "NOTIF_PAGO_OBSERVADO" if id == observado else "NOTIF_PAGO_RECHAZADO"
        revisado = ids_evento[(id, "PagoRevisadoEvent")]
        assert indice[(id, tipo)].evento_id == UUID(revisado.payload["event_id"])
        assert revisado.comprobante_id == UUID(id)


async def test_evento_sin_saldo_resultante_queda_como_incidencia(api_pagos):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    id = await reportar_id(client, usuario, "OP-INCOMPLETO", "100.00")
    assert (await revisar(client, junta, id, "APROBADO", None)).status_code == 200
    async with base.sessions() as db, db.begin():
        evento = await db.scalar(
            select(EventoPagoOutbox).where(
                EventoPagoOutbox.payload["event_type"].astext == "PagoConciliadoEvent"
            )
        )
        data = {k: v for k, v in evento.payload["data"].items() if k != "nuevo_saldo_departamento"}
        evento.payload = {**evento.payload, "data": data}
        payload = evento.payload
    assert await consumir(base.sessions, payload) is None
    await base.engine.dispose()
    async with base.sessions() as db:
        incidencia = await db.scalar(select(IncidenciaEvento))
        assert incidencia.motivo == "DATOS_PLANTILLA_INCOMPLETOS"
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 0
        assert await db.scalar(select(func.count()).select_from(EventoConsumido)) == 0
