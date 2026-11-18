"""Brechas puntuales CON-25–28: SQL real; transporte externo solo simulado.

Reutiliza el productor y las fixtures de Sprint 3 con autoflush=False.
No añade motores, migraciones ni llamadas a proveedores reales de correo.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import IntentoNotificacion, Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_persistencia import EventoPagoOutbox, RevisionPago
from src.modules.reservas.models import EventoReservaOutbox, Reserva
from src.tests.integration.test_aislamiento_con77_db import huella
from src.tests.integration.test_pagos_db import solicitud
from src.tests.pagos_db import did
from src.tests.pagos_sprint3 import reportar, revisar
from src.tests.pagos_sprint3 import sistema as sistema

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


@pytest.mark.parametrize("sistema", [{}, {"diaria": True}], indirect=True)
async def test_parcial_bloquea_reserva_real_y_completar_deuda_la_habilita(sistema):
    client, base, cuota_id, residente, junta = sistema
    pid = await reportar(client, residente, "40.00")
    parcial = await revisar(client, junta, pid)
    assert parcial.status_code == 200, parcial.text
    assert parcial.json()["departamento_habilitado_reservas"] is False
    async with base.sessions() as db:
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        diaria = cuota.politica_mora_aplicada is not None
        assert cuota.monto_pagado == Decimal("40.00")
        assert cuota.estado == "EN_MORA"
    # Un parcial diario oportuno no condona los días posteriores con principal impago.
    pendiente = "70.00" if diaria else "60.00"
    assert parcial.json()["nuevo_saldo_departamento"] == pendiente
    body = solicitud(base, numero="102")
    bloqueada = await client.post("/api/v1/reservas", headers=residente, json=body)
    assert bloqueada.status_code == 403, bloqueada.text
    assert bloqueada.json()["error_code"] == "DEUDA_MORA_ACTIVA"
    async with base.sessions() as db:
        assert await db.scalar(select(Reserva.id)) is None
        assert await db.scalar(select(EventoReservaOutbox.id)) is None
    segundo = await reportar(client, residente, pendiente, "2026-10-20")
    final = await revisar(client, junta, segundo)
    assert final.status_code == 200, final.text
    assert final.json()["nuevo_saldo_departamento"] == "0.00"
    assert final.json()["saldo_a_favor_generado"] == "0.00"
    confirmada = await client.post("/api/v1/reservas", headers=residente, json=body)
    assert confirmada.status_code == 201, confirmada.text
    await base.engine.dispose()
    async with base.sessions() as db:
        cuota = await db.get(CuotaMantenimiento, cuota_id)
        assert cuota.estado == "PAGADA" and cuota.monto_pagado == cuota.monto_total_exigible
        reserva = await db.get(Reserva, UUID(confirmada.json()["id"]))
        assert reserva.estado == "CONFIRMADA" and reserva.departamento_id == did("102")
        eventos = list(await db.scalars(select(EventoReservaOutbox)))
        assert len(eventos) == 1 and eventos[0].tipo == "ReservaConfirmadaEvent"
        assert eventos[0].reserva_id == reserva.id


async def test_liquidar_una_cuota_no_habilita_reserva_con_otra_deuda_vencida(sistema):
    client, base, cuota_actual_id, residente, junta = sistema
    vieja_id = uuid4()
    async with base.sessions() as db, db.begin():
        db.add(
            CuotaMantenimiento(
                id=vieja_id,
                departamento_id=did("102"),
                periodo="2026-09",
                fecha_emision=date(2026, 9, 1),
                fecha_vencimiento=date(2026, 9, 10),
                monto_ordinario=Decimal("30.00"),
                monto_total_exigible=Decimal("30.00"),
                monto_pagado=Decimal("0.00"),
                estado="EN_MORA",
                dias_gracia_aplicados=0,
            )
        )
    pid = await reportar(client, residente, "30.00")
    r = await revisar(client, junta, pid)
    assert r.status_code == 200, r.text
    assert r.json()["nuevo_saldo_departamento"] == "100.00"
    assert r.json()["departamento_habilitado_reservas"] is False
    async with base.sessions() as db:
        assert (await db.get(CuotaMantenimiento, vieja_id)).estado == "PAGADA"
        assert (await db.get(CuotaMantenimiento, cuota_actual_id)).monto_pagado == 0
    bloqueada = await client.post(
        "/api/v1/reservas",
        headers=residente,
        json=solicitud(base, numero="102"),
    )
    assert bloqueada.status_code == 403 and bloqueada.json()["error_code"] == "DEUDA_MORA_ACTIVA"
    async with base.sessions() as db:
        assert await db.scalar(select(Reserva.id)) is None
        assert await db.scalar(select(EventoReservaOutbox.id)) is None


@pytest.mark.parametrize("decision", ["APROBADO", "OBSERVADO", "RECHAZADO"])
async def test_revision_legacy_sin_archivo_recupera_recibo_sin_reaplicar(sistema, decision):
    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente)
    campos = {} if decision == "APROBADO" else {"motivo_rechazo": "Motivo histórico"}
    original = await revisar(client, junta, pid, decision, **campos)
    assert original.status_code == 200, original.text
    async with base.sessions() as db, db.begin():
        revision = await db.scalar(
            select(RevisionPago).where(
                RevisionPago.comprobante_id == UUID(pid),
            )
        )
        # Fixture de compatibilidad: simula la referencia nullable anterior a CON-72.
        # El archivo vigente del comprobante se conserva; no se borra evidencia.
        revision.archivo_nombre = None
    antes = await huella(base)
    recuperado = await client.get(f"/api/v1/pagos/{pid}/resultado", headers=residente)
    assert recuperado.status_code == 200, recuperado.text
    assert recuperado.json() == original.json()
    repetido = await revisar(client, junta, pid, decision, **campos)
    assert repetido.status_code == 200 and repetido.json() == original.json()
    assert await huella(base) == antes


async def fotografia_financiera(base):
    """Compara finanzas/auditoría/outbox, sin confundirlos con intentos de transporte."""
    tablas = (
        ComprobantePago,
        ImputacionPago,
        RevisionPago,
        CuotaMantenimiento,
        Departamento,
        AuditoriaLogORM,
        EventoPagoOutbox,
    )
    async with base.sessions() as db:
        return {
            model.__tablename__: (
                await db.execute(
                    select(model.__table__).order_by(*model.__table__.primary_key.columns),
                )
            ).all()
            for model in tablas
        }


@pytest.mark.parametrize("decision", ["OBSERVADO", "RECHAZADO"])
async def test_fallo_y_reintento_transporte_no_revierten_ni_duplican_revision(sistema, decision):
    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente)
    campos = {"motivo_rechazo": "Verifique la operación", "notas_internas": "SOLO_ADMIN"}
    revisado = await revisar(client, junta, pid, decision, **campos)
    assert revisado.status_code == 200, revisado.text
    async with base.sessions() as db:
        evento = await db.scalar(
            select(EventoPagoOutbox).where(
                EventoPagoOutbox.payload["event_type"].astext == "PagoRevisadoEvent",
            )
        )
        payload = evento.payload
    assert await consumir(base.sessions, payload) == 1
    assert await consumir(base.sessions, payload) == 0
    antes = await fotografia_financiera(base)
    ahora = datetime.now(UTC)
    llamadas = []

    def fallar(log, clave):
        llamadas.append((log.id, clave))
        raise TimeoutError("Fallo sintético sin conexión a un proveedor externo")

    assert await procesar_uno(base.sessions, transport=fallar, ahora=ahora, jitter=lambda *_: 0)
    assert len(llamadas) == 1
    assert await fotografia_financiera(base) == antes
    async with base.sessions() as db:
        aviso = await db.scalar(select(Notificacion))
        assert aviso.transporte == "SIMULADO"
        assert aviso.estado == "REINTENTANDO" and aviso.intentos == 1
        assert "SOLO_ADMIN" not in aviso.cuerpo
        aviso_id, siguiente = aviso.id, aviso.proximo_reintento
        assert siguiente == ahora + timedelta(minutes=2)
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 1
    recuperado = await client.get(f"/api/v1/pagos/{pid}/resultado", headers=residente)
    assert recuperado.status_code == 200 and recuperado.json() == revisado.json()
    # No reenvía antes de su fecha, ni crea otro intento por una pasada del worker.
    assert not await procesar_uno(base.sessions, ahora=ahora)
    assert await procesar_uno(base.sessions, ahora=siguiente)
    assert not await procesar_uno(base.sessions, ahora=siguiente + timedelta(seconds=1))
    assert await consumir(base.sessions, payload) == 0
    assert await fotografia_financiera(base) == antes
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1
        aviso = await db.get(Notificacion, aviso_id)
        assert aviso.estado == "ENVIADO" and aviso.intentos == 2
        assert aviso.transporte == "SIMULADO"  # ENVIADO simulado no acredita correo real.
        intentos = list(
            await db.scalars(select(IntentoNotificacion).order_by(IntentoNotificacion.numero))
        )
        assert [i.numero for i in intentos] == [1, 2]
        assert all(i.notificacion_id == aviso_id and i.terminado_en for i in intentos)
    repetido = await revisar(client, junta, pid, decision, **campos)
    assert repetido.status_code == 200 and repetido.json() == revisado.json()
    assert await fotografia_financiera(base) == antes
