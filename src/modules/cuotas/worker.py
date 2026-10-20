"""Worker independiente: emisión mensual recuperable y relay outbox a Redis Streams."""

import asyncio
import json
import logging
import signal
from datetime import UTC, date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.errors import APIError
from src.modules.condominios.models import Condominio
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.models import EventoLoteOutbox
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.saldos.service import ActorSaldoFavor
from src.modules.cuotas.schemas import EmitirLoteRequest

logger = logging.getLogger(__name__)
STREAM = "condomanager:domain-events"


async def emitir_pendientes(session_factory=AsyncSessionLocal, hoy: date | None = None):
    hoy = hoy or datetime.now(UTC).date()
    if hoy.day < settings.CUOTAS_DIA_EMISION:
        return
    periodo = hoy.strftime("%Y-%m")
    async with session_factory() as session:
        ids = list(
            (
                await session.scalars(
                    select(Condominio.id)
                    .join(PresupuestoMensual)
                    .where(
                        Condominio.activo.is_(True),
                        PresupuestoMensual.periodo == periodo,
                        PresupuestoMensual.estado == "APROBADO",
                    )
                    .order_by(Condominio.id)
                )
            ).all()
        )
    for cid in ids:
        try:
            async with session_factory() as session:
                await EmisionCuotasService(session).emitir(
                    EmitirLoteRequest(condominio_id=cid, periodo=periodo),
                    ActorSaldoFavor("CON11_WORKER", "SISTEMA_AUTOMATICO", cid),
                )
        except APIError as exc:
            if exc.error_code != "LOTE_YA_EMITIDO":
                logger.exception(
                    "Emisión pendiente fallida: condominio=%s periodo=%s", cid, periodo
                )
        except Exception:
            logger.exception("Emisión pendiente fallida: condominio=%s periodo=%s", cid, periodo)


async def publicar_pendientes(redis, session_factory=AsyncSessionLocal):
    # Límite por pasada; los locks evitan que dos relays publiquen simultáneamente una fila.
    for _ in range(100):
        async with session_factory() as session, session.begin():
            evento = await session.scalar(
                select(EventoLoteOutbox)
                .where(EventoLoteOutbox.publicado_en.is_(None))
                .order_by(EventoLoteOutbox.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if evento is None:
                return
            await redis.xadd(STREAM, {"event": json.dumps(evento.payload)})
            # Si cae el proceso antes del commit, se republica con el mismo event_id.
            evento.publicado_en = datetime.now(UTC)


async def main():
    logging.basicConfig(level=logging.INFO)
    detener = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, detener.set)
    redis = Redis.from_url(settings.REDIS_URL, socket_timeout=10, socket_connect_timeout=10)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        emitir_pendientes,
        "cron",
        hour=0,
        minute=0,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        publicar_pendientes, "interval", seconds=30, args=[redis], coalesce=True, max_instances=1
    )
    scheduler.start()
    try:
        await emitir_pendientes()
        await detener.wait()
    finally:
        scheduler.shutdown(wait=False)
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
