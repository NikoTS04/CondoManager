import pytest
from sqlalchemy import select

from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import IntentoNotificacion, Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.tests.integration.test_reservas_notificaciones_db import evento, reservar

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def test_aceptacion_incierta_no_se_reintenta_ciegamente(api_usuarios):
    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    llamadas = []
    def incierto(log, clave):
        llamadas.append(clave)
        return {"status": 0, "incierto": True}
    assert await procesar_uno(base.sessions, transport=incierto)
    assert not await procesar_uno(base.sessions, transport=incierto)
    assert len(llamadas) == 1
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        intento = await db.scalar(select(IntentoNotificacion))
        assert log.estado == "FALLIDO_PERMANENTE"
        assert log.proximo_reintento is None and log.proveedor_message_id is None
        assert log.error_mensaje == intento.error == "ACEPTACION_INCIERTA"
