"""Relay recuperable de CON-70 y limpieza de subidas abandonadas de CON-22."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.pagos.models_persistencia import ArchivoVoucher, EventoPagoOutbox
from src.modules.pagos.storage import NOMBRE, VoucherStorage

logger = logging.getLogger(__name__)
STREAM = "condomanager:domain-events"


async def publicar_pendientes(redis, session_factory=AsyncSessionLocal):
    for _ in range(100):
        async with session_factory() as session, session.begin():
            evento = await session.scalar(
                select(EventoPagoOutbox)
                .where(EventoPagoOutbox.publicado_en.is_(None))
                .order_by(EventoPagoOutbox.creado_en, EventoPagoOutbox.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if evento is None:
                return
            await redis.xadd(STREAM, {"event": json.dumps(evento.payload)})
            evento.publicado_en = datetime.now(UTC)


async def limpiar_pendientes(
    session_factory=AsyncSessionLocal,
    storage: VoucherStorage | None = None,
    ahora: datetime | None = None,
):
    storage = storage or VoucherStorage()
    limite = (ahora or datetime.now(UTC)) - timedelta(hours=24)
    for _ in range(100):
        async with session_factory() as session, session.begin():
            subida = await session.scalar(
                select(ArchivoVoucher)
                .where(ArchivoVoucher.comprobante_id.is_(None), ArchivoVoucher.creado_en < limite)
                .order_by(ArchivoVoucher.creado_en)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if subida is None:
                break
            await asyncio.to_thread(storage.eliminar, subida.nombre)
            await session.delete(subida)
    # Interrupción entre escritura y registro SQL: recuperar archivos no registrados.
    # La consulta SQL es obligatoria; si la BD está caída nunca se borra evidencia.
    if not storage.directorio.exists():
        return
    for ruta in storage.directorio.iterdir():
        if not NOMBRE.fullmatch(ruta.name) or ruta.is_symlink() or not ruta.is_file():
            continue
        if datetime.fromtimestamp(ruta.stat().st_mtime, UTC) >= limite:
            continue
        async with session_factory() as session:
            subida = await session.get(ArchivoVoucher, ruta.name)
            if subida is None:
                # Una referencia preexistente también es evidencia, aunque no tenga subida.
                from src.modules.pagos.models import ComprobantePago

                referencia = await session.scalar(
                    select(ComprobantePago.id)
                    .where(ComprobantePago.url_voucher == ruta.name)
                    .limit(1)
                )
                if referencia is None:
                    await asyncio.to_thread(storage.eliminar, ruta.name)


async def main():
    logging.basicConfig(level=logging.INFO)
    redis = Redis.from_url(settings.REDIS_URL, socket_timeout=10, socket_connect_timeout=10)
    try:
        while True:
            try:
                await publicar_pendientes(redis)
                await limpiar_pendientes()
            except Exception:
                logger.exception("Relay de pagos pendiente: se recuperará en la siguiente pasada.")
            await asyncio.sleep(30)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
