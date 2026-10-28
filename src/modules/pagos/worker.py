"""Relay recuperable de CON-70 y limpieza de subidas abandonadas de CON-22."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.pagos.fondos_models import EventoFondoMorasOutbox
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.models_mora import EventoMoraOutbox
from src.modules.pagos.models_persistencia import ArchivoVoucher, EventoPagoOutbox
from src.modules.pagos.mora_diaria import MoraDiariaService
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.storage import NOMBRE, VoucherStorage
from src.shared.fechas import fecha_lima

logger = logging.getLogger(__name__)
STREAM = "condomanager:domain-events"


async def publicar_pendientes(redis, session_factory=AsyncSessionLocal):
    for modelo in (EventoPagoOutbox, EventoMoraOutbox, EventoFondoMorasOutbox):
        for _ in range(100):
            async with session_factory() as session, session.begin():
                evento = await session.scalar(
                    select(modelo)
                    .where(modelo.publicado_en.is_(None))
                    .order_by(modelo.creado_en, modelo.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if evento is None:
                    break
                await redis.xadd(STREAM, {"event": json.dumps(evento.payload)})
                evento.publicado_en = datetime.now(UTC)


async def evaluar_moras_diarias(session_factory=AsyncSessionLocal, hoy=None, ahora=None):
    hoy = hoy or fecha_lima()
    async with session_factory() as session:
        unidades = list((await session.execute(
            select(Condominio.id, Departamento.id).select_from(Condominio).join(Edificio).join(Departamento)
            .join(CuotaMantenimiento)
            .where(Condominio.activo.is_(True),
                   CuotaMantenimiento.politica_mora_aplicada["modalidad"].astext == "MONTO_DIARIO")
            .distinct().order_by(Condominio.id, Departamento.id)
        )).all())
    for cid, did in unidades:
        try:
            async with session_factory() as session, session.begin():
                condominio = await session.scalar(select(Condominio).where(Condominio.id == cid).with_for_update())
                if condominio is None or not condominio.activo:
                    continue
                departamento = await session.scalar(select(Departamento).join(Edificio).where(
                    Departamento.id == did, Edificio.condominio_id == cid).with_for_update(of=Departamento))
                if departamento is None:
                    continue
                cuotas = await SQLAlchemyPagosRepository(session).cuotas(did, bloquear=True)
                await MoraDiariaService(session).reconstruir(
                    departamento, condominio, cuotas, {"sub": "MORA_DIARIA_WORKER", "rol": "SISTEMA_AUTOMATICO"},
                    hoy, ahora=ahora,
                )
        except Exception:
            logger.exception("Mora diaria pendiente: condominio=%s departamento=%s", cid, did)


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
    scheduler = AsyncIOScheduler(timezone="America/Lima")
    scheduler.add_job(evaluar_moras_diarias, "cron", hour=0, minute=5,
                      coalesce=True, max_instances=1, misfire_grace_time=3600)
    scheduler.start()
    try:
        await evaluar_moras_diarias()
        while True:
            try:
                await publicar_pendientes(redis)
                await limpiar_pendientes()
            except Exception:
                logger.exception("Relay de pagos pendiente: se recuperará en la siguiente pasada.")
            await asyncio.sleep(30)
    finally:
        scheduler.shutdown(wait=False)
        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
