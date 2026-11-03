"""CON-78: cola SQL con transporte PROVEEDOR (SMTP) sobre PostgreSQL real.

El proveedor se sustituye por un callable; el adaptador SMTP se prueba aparte.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.core.config import settings
from src.modules.notificaciones.models import IntentoNotificacion, Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.tests.integration.test_alertas_notificaciones_db import (
    SIN_JITTER,
    alertas,
    encolar,
    estado,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


@pytest.fixture
def smtp_activo(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_TRANSPORTE", "SMTP")


async def fila(base, nid):
    async with base.sessions() as db:
        log = await db.get(Notificacion, nid)
        intentos = list(
            await db.scalars(
                select(IntentoNotificacion)
                .where(IntentoNotificacion.notificacion_id == nid)
                .order_by(IntentoNotificacion.numero)
            )
        )
        return log, intentos


def proveedor(*resultados):
    llamadas = []
    pendientes = list(resultados)

    def enviar(log, clave):
        llamadas.append((log.destinatario, clave))
        return pendientes.pop(0)

    enviar.llamadas = llamadas
    return enviar


def simulado_prohibido(*_):
    pytest.fail("un mensaje PROVEEDOR no debe usar el transporte simulado")


async def test_con_smtp_configurado_email_se_encola_como_proveedor(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    log, _ = await fila(base, nid)
    assert log.transporte == "PROVEEDOR"


async def test_sin_smtp_el_email_sigue_simulado(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    log, _ = await fila(base, nid)
    assert log.transporte == "SIMULADO"


async def test_aceptacion_del_proveedor_queda_enviado_con_referencia(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    enviar = proveedor({"status": 200, "message_id": "<ref@condo.test>"})
    assert await procesar_uno(base.sessions, simulado_prohibido, proveedor=enviar)
    log, [intento] = await fila(base, nid)
    # SMTP acredita aceptación, no entrega en el buzón.
    assert (log.estado, log.intentos) == ("ENVIADO", 1)
    assert log.proveedor_message_id == intento.proveedor_message_id == "<ref@condo.test>"
    assert enviar.llamadas == [("ana@ejemplo.test", f"{nid}-1-1")]
    assert not await procesar_uno(base.sessions, simulado_prohibido, proveedor=enviar)


async def test_fallo_temporal_reintenta_con_clave_nueva(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    enviar = proveedor(
        {"status": 503, "error": "FALLO_TEMPORAL"}, {"status": 200, "message_id": "<r2@x>"}
    )
    ahora = datetime.now(UTC)
    assert await procesar_uno(
        base.sessions, simulado_prohibido, ahora=ahora, proveedor=enviar, **SIN_JITTER
    )
    assert await estado(base, nid) == ("REINTENTANDO", 1)
    assert await procesar_uno(
        base.sessions, simulado_prohibido, ahora=ahora + timedelta(minutes=2), proveedor=enviar
    )
    _, intentos = await fila(base, nid)
    assert [i.error for i in intentos] == ["FALLO_TEMPORAL", None]
    assert [c for _, c in enviar.llamadas] == [f"{nid}-1-1", f"{nid}-1-2"]
    assert await alertas(base, nid) == []


async def test_rebote_del_proveedor_es_definitivo_con_alerta(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    enviar = proveedor({"status": 550, "error": "550"})
    assert await procesar_uno(base.sessions, simulado_prohibido, proveedor=enviar)
    assert await estado(base, nid) == ("FALLIDO_PERMANENTE", 1)
    [alerta] = await alertas(base, nid)
    assert alerta.tipo == "ERROR_DEFINITIVO"


async def test_aceptacion_incierta_no_reenvia_y_alerta(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    enviar = proveedor({"status": 0, "error": "ACEPTACION_INCIERTA", "incierto": True})
    ahora = datetime.now(UTC)
    assert await procesar_uno(base.sessions, simulado_prohibido, ahora=ahora, proveedor=enviar)
    log, [intento] = await fila(base, nid)
    assert log.estado == "FALLIDO_PERMANENTE"
    assert log.error_mensaje == "ACEPTACION_INCIERTA_REQUIERE_REVISION"
    assert intento.error == "ACEPTACION_INCIERTA" and intento.terminado_en is not None
    [alerta] = await alertas(base, nid)
    assert alerta.tipo == "ACEPTACION_INCIERTA"
    # Ni siquiera días después se reenvía solo.
    assert not await procesar_uno(
        base.sessions, simulado_prohibido, ahora=ahora + timedelta(days=1), proveedor=enviar
    )
    assert len(enviar.llamadas) == 1


async def test_excepcion_del_proveedor_es_temporal(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")

    def roto(*_):
        raise RuntimeError("fallo interno")

    assert await procesar_uno(base.sessions, simulado_prohibido, proveedor=roto, **SIN_JITTER)
    assert await estado(base, nid) == ("REINTENTANDO", 1)


async def test_mensaje_proveedor_sin_configuracion_no_usa_simulado(api_usuarios, smtp_activo):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    # Worker sin SMTP_HOST: el mensaje real queda fallido y alertado, nunca ENVIADO simulado.
    assert await procesar_uno(base.sessions, simulado_prohibido)
    log, intentos = await fila(base, nid)
    assert (log.estado, log.error_mensaje, intentos) == (
        "FALLIDO_PERMANENTE",
        "PROVEEDOR_NO_CONFIGURADO",
        [],
    )
