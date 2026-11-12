"""Relay recuperable de ReservaCanceladaEvent hacia el stream de CON-36.

Entrega al menos una vez. El consumidor deduplica por event_id; publicar en
Redis no acredita entrega de correo ni aplicación de una compensación.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Departamento  # noqa: F401 — registrar FK
from src.modules.reservas.models import EventoReservaOutbox

logger = logging.getLogger(__name__)
STREAM = "condomanager:domain-events"


async def publicar_pendientes(redis, session_factory=AsyncSessionLocal):
    for _ in range(100):
        async with session_factory() as session, session.begin():
            evento = await session.scalar(
                select(EventoReservaOutbox)
                .where(EventoReservaOutbox.publicado_en.is_(None))
                .order_by(EventoReservaOutbox.creado_en, EventoReservaOutbox.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if evento is None:
                return
            await redis.xadd(STREAM, {"event": json.dumps(evento.payload)})
            evento.publicado_en = datetime.now(UTC)


async def main():
    redis = Redis.from_url(settings.REDIS_URL, socket_timeout=10, socket_connect_timeout=10)
    try:
        while True:
            try:
                await publicar_pendientes(redis)
            except Exception:
                logger.exception("Cancelaciones pendientes: se reintentará la publicación.")
            await asyncio.sleep(30)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
