from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones import mailjet
from src.modules.notificaciones.eventos_mailjet import EventoMailjet, aplicar_evento
from src.modules.notificaciones.models import AlertaNotificacion, IntentoNotificacion, Notificacion
from src.modules.notificaciones.recordatorios import generar_recordatorios
from src.modules.notificaciones.worker import procesar_uno
from src.tests.integration.test_alertas_notificaciones_db import encolar
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def test_cola_real_callback_duplicado_y_rebote(api_usuarios, monkeypatch):
    client, base = api_usuarios
    # El historial simulado nunca se promueve al activar el proveedor.
    historico, _ = await encolar(client, base, "destino@example.test")
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    nid, _ = await encolar(client, base, "destino@example.test")
    recibidos = []

    def enviar(log, clave):
        recibidos.append((log.id, clave))
        return {"status": 200, "message_id": "123"}

    monkeypatch.setattr(mailjet, "transporte_mailjet", enviar)
    assert await procesar_uno(base.sessions, solo_proveedor=True)
    assert not await procesar_uno(base.sessions, solo_proveedor=True)
    assert len(recibidos) == 1 and recibidos[0][0] == nid
    evento = EventoMailjet(event="sent", MessageID=123, CustomID=recibidos[0][1], email="destino@example.test")
    await aplicar_evento(evento, base.sessions)
    await aplicar_evento(evento, base.sessions)
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid)).estado == "ENTREGADO"
        assert (await db.get(Notificacion, historico)).estado == "EN_COLA"
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM).where(
            AuditoriaLogORM.accion_ejecutada == "NOTIFICACION_RESULTADO_MAILJET"
        )) == 1
    await aplicar_evento(evento.model_copy(update={"event": "bounce", "MessageID": 999}), base.sessions)
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid)).estado == "ENTREGADO"
    await aplicar_evento(evento.model_copy(update={"event": "bounce"}), base.sessions)
    await aplicar_evento(evento, base.sessions)
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid)).estado == "FALLIDO_PERMANENTE"
        assert await db.scalar(select(func.count()).select_from(AlertaNotificacion)) == 1


async def test_callback_antes_de_respuesta_y_ciclo_antiguo(api_usuarios, monkeypatch):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    nid, _ = await encolar(client, base, "destino@example.test")
    async with base.sessions() as db, db.begin():
        log = await db.get(Notificacion, nid)
        log.intentos = 1
        db.add(IntentoNotificacion(
            notificacion_id=nid, ciclo=1, numero=1, iniciado_en=datetime.now(UTC)
        ))
    evento = EventoMailjet(event="sent", MessageID=123, CustomID=f"{nid}-1-1", email="destino@example.test")
    await aplicar_evento(evento, base.sessions)
    async with base.sessions() as db, db.begin():
        log = await db.get(Notificacion, nid)
        assert log.estado == "ENTREGADO" and log.proveedor_message_id == "123"
        log.ciclo = 2
        log.intentos = 0
        log.estado = "EN_COLA"
    await aplicar_evento(evento.model_copy(update={"event": "bounce"}), base.sessions)
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid)).estado == "EN_COLA"


@pytest.mark.parametrize("excepcion", [False, True])
async def test_incierto_no_se_reenvia_y_deshabilitado_no_consume(api_usuarios, monkeypatch, excepcion):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    nid, _ = await encolar(client, base, "destino@example.test")
    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)
    assert not await procesar_uno(base.sessions, solo_proveedor=True)
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid)).intentos == 0
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    def enviar(*args):
        if excepcion:
            raise TimeoutError("aceptación desconocida")
        return {"status": 0, "incierto": True}
    monkeypatch.setattr(mailjet, "transporte_mailjet", enviar)
    assert await procesar_uno(base.sessions, solo_proveedor=True)
    assert not await procesar_uno(base.sessions, solo_proveedor=True)
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid)).error_mensaje == "ACEPTACION_INCIERTA"


@pytest.mark.parametrize("dias", [0, 3])
async def test_recordatorio_deduplicado_y_pagado_no_envia(api_usuarios, monkeypatch, dias):
    _, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    ahora = datetime(2026, 11, 21, 13, tzinfo=UTC)
    cuota = CuotaMantenimiento(
        departamento_id=did("102"), periodo="2026-11", monto_ordinario=100,
        monto_total_exigible=100, fecha_emision=ahora.date(),
        fecha_vencimiento=ahora.date() + timedelta(days=dias),
    )
    async with base.sessions() as db, db.begin():
        db.add(cuota)
    await generar_recordatorios(base.sessions, ahora - timedelta(minutes=1))
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 0
    await generar_recordatorios(base.sessions, ahora)
    await generar_recordatorios(base.sessions, ahora)
    async with base.sessions() as db, db.begin():
        total = await db.scalar(select(func.count()).select_from(Notificacion))
        assert total > 0
        assert await db.scalar(select(func.count(func.distinct(Notificacion.usuario_destinatario_id)))) == total
        (await db.get(CuotaMantenimiento, cuota.id)).monto_pagado = 100
    while await procesar_uno(base.sessions, transport=lambda *a: pytest.fail("cuota pagada")):
        pass
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 0


async def test_rechazo_429_respeta_umbral_y_reintenta(api_usuarios, monkeypatch):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    nid, _ = await encolar(client, base, "destino@example.test")
    respuestas = iter([{"status": 429}, {"status": 200, "message_id": "123"}])
    monkeypatch.setattr(mailjet, "transporte_mailjet", lambda *a: next(respuestas))
    ahora = datetime.now(UTC)
    assert await procesar_uno(base.sessions, solo_proveedor=True, ahora=ahora, jitter=lambda *a: 0)
    async with base.sessions() as db:
        log = await db.get(Notificacion, nid)
        assert log.estado == "REINTENTANDO" and log.intentos == 1
    assert not await procesar_uno(
        base.sessions, solo_proveedor=True, ahora=ahora + timedelta(seconds=119)
    )
    assert await procesar_uno(
        base.sessions, solo_proveedor=True, ahora=ahora + timedelta(minutes=2)
    )
    async with base.sessions() as db:
        log = await db.get(Notificacion, nid)
        assert log.estado == "ENVIADO" and log.intentos == 2
