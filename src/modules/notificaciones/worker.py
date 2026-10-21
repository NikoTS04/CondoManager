"""Worker asíncrono de notificaciones: consumo de Redis Streams y despacho (CON-32/34/36/37).

1. Consume `condomanager:domain-events` mediante grupo de consumidores (`XREADGROUP`).
2. Confirma cada mensaje (`XACK`) únicamente después del commit en PostgreSQL.
3. Recupera mensajes pendientes tras reinicios con `XAUTOCLAIM` y lectura de `0`.
4. Ejecuta periódicamente `entrega.despachar_pendientes` para enviar notificaciones en cola.
"""

import asyncio
import json
import logging
import os
import signal
import socket
import uuid
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.notificaciones.consumidores import (
    MANEJADORES_EVENTOS,
    ErrorContratoEvento,
    consumir_evento,
)
from src.modules.notificaciones.entrega import despachar_pendientes

logger = logging.getLogger(__name__)

STREAM = "condomanager:domain-events"
GROUP = "notificaciones-workers"
# En contenedores el pid suele ser 1: el hostname y un sufijo aleatorio distinguen réplicas,
# requisito para que el arrendamiento `bloqueado_por` identifique a cada worker.
WORKER_ID_DEFAULT = f"notif-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"[:80]


def _decodificar_texto(valor: Any) -> str:
    if isinstance(valor, bytes):
        return valor.decode("utf-8")
    return str(valor)


def _extraer_envelope(campos: dict[Any, Any]) -> dict[str, Any]:
    raw = campos.get("event")
    if raw is None:
        raw = campos.get(b"event")
    if raw is None:
        raise ValueError("El mensaje del stream no contiene el campo 'event'.")
    if isinstance(raw, dict):
        return raw
    texto = _decodificar_texto(raw)
    datos = json.loads(texto)
    if not isinstance(datos, dict):
        raise ValueError("El payload JSON del campo 'event' debe ser un objeto.")
    return datos


async def asegurar_grupo_consumidor(
    redis: Redis,
    stream: str = STREAM,
    group: str = GROUP,
) -> None:
    """Crea el grupo de consumidores e inicializa el stream si no existen."""
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def procesar_mensaje_stream(
    redis: Redis,
    session_factory=AsyncSessionLocal,
    mensaje_id: str | bytes = "",
    campos: dict[Any, Any] | None = None,
    *,
    stream: str = STREAM,
    group: str = GROUP,
) -> bool:
    """Procesa un mensaje en una transacción y ejecuta XACK solo después del commit.

    Los eventos de otros dominios se confirman sin efecto. Un mensaje que incumple el
    contrato no mejorará al reintentarlo: se copia a la DLQ y se confirma. Cualquier otro
    fallo (BD, red) queda pendiente para XAUTOCLAIM.
    """
    msg_id_str = _decodificar_texto(mensaje_id)
    try:
        envelope = _extraer_envelope(campos or {})
        if envelope.get("event_type") not in MANEJADORES_EVENTOS:
            await redis.xack(stream, group, msg_id_str)
            return True
        async with session_factory() as session:
            await consumir_evento(session, envelope)
        await redis.xack(stream, group, msg_id_str)
        return True
    except (ErrorContratoEvento, ValueError) as exc:
        logger.error("Evento %s rechazado por contrato; se envía a DLQ: %s", msg_id_str, exc)
        await redis.xadd(
            f"{stream}:dlq",
            {
                "origen": msg_id_str,
                "error": str(exc)[:500],
                "event": json.dumps(campos or {}, default=_decodificar_texto),
            },
        )
        await redis.xack(stream, group, msg_id_str)
        return False
    except Exception:
        logger.exception("Fallo procesando mensaje %s de %s (sin XACK)", msg_id_str, stream)
        return False


async def recuperar_pendientes_stream(
    redis: Redis,
    session_factory=AsyncSessionLocal,
    *,
    stream: str = STREAM,
    group: str = GROUP,
    consumer: str = WORKER_ID_DEFAULT,
    min_idle_ms: int = 0,
    count: int = 50,
) -> int:
    """Recupera mensajes pendientes (PEL) tras un reinicio mediante XAUTOCLAIM y lectura de '0'."""
    await asegurar_grupo_consumidor(redis, stream=stream, group=group)
    mensajes_pendientes: list[tuple[Any, dict[Any, Any]]] = []
    vistos: set[str] = set()

    try:
        reclamados = await redis.xautoclaim(
            stream,
            group,
            consumer,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=count,
        )
        # En Redis 6.2+/7 xautoclaim devuelve (next_id, [(msg_id, fields), ...], [deleted_ids])
        entradas = (
            reclamados[1] if isinstance(reclamados, (list, tuple)) and len(reclamados) > 1 else []
        )
        for msg_id, fields in entradas:
            if fields:
                clave_id = _decodificar_texto(msg_id)
                if clave_id not in vistos:
                    vistos.add(clave_id)
                    mensajes_pendientes.append((msg_id, fields))
    except ResponseError:
        logger.debug("XAUTOCLAIM no disponible; usando lectura de pendientes '0'.")

    prop_pendientes = await redis.xreadgroup(
        groupname=group,
        consumername=consumer,
        streams={stream: "0"},
        count=count,
    )
    for _stream_name, entradas in prop_pendientes or []:
        for msg_id, fields in entradas:
            if not fields:
                continue
            clave_id = _decodificar_texto(msg_id)
            if clave_id not in vistos:
                vistos.add(clave_id)
                mensajes_pendientes.append((msg_id, fields))

    confirmados = 0
    for msg_id, fields in mensajes_pendientes:
        ok = await procesar_mensaje_stream(
            redis,
            session_factory,
            msg_id,
            fields,
            stream=stream,
            group=group,
        )
        if ok:
            confirmados += 1
    return confirmados


async def consumir_lote_stream(
    redis: Redis,
    session_factory=AsyncSessionLocal,
    *,
    stream: str = STREAM,
    group: str = GROUP,
    consumer: str = WORKER_ID_DEFAULT,
    count: int = 50,
    block_ms: int | None = 1000,
) -> int:
    """Lee mensajes nuevos ('>') con XREADGROUP y ejecuta XACK solo tras commit."""
    await asegurar_grupo_consumidor(redis, stream=stream, group=group)
    respuesta = await redis.xreadgroup(
        groupname=group,
        consumername=consumer,
        streams={stream: ">"},
        count=count,
        block=block_ms,
    )
    confirmados = 0
    for _stream_name, entradas in respuesta or []:
        for msg_id, fields in entradas:
            ok = await procesar_mensaje_stream(
                redis,
                session_factory,
                msg_id,
                fields,
                stream=stream,
                group=group,
            )
            if ok:
                confirmados += 1
    return confirmados


async def ejecutar_ciclo_despacho(
    session_factory=AsyncSessionLocal,
    transporte=None,
    worker_id: str = WORKER_ID_DEFAULT,
    ahora: datetime | None = None,
):
    """Invoca `entrega.despachar_pendientes` para enviar las notificaciones en cola."""
    return await despachar_pendientes(
        session_factory=session_factory,
        transporte=transporte,
        worker_id=worker_id,
        ahora=ahora,
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    detener = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, detener.set)

    worker_id = WORKER_ID_DEFAULT
    redis = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=10,
        socket_connect_timeout=10,
    )
    await asegurar_grupo_consumidor(redis, stream=STREAM, group=GROUP)
    await recuperar_pendientes_stream(redis, AsyncSessionLocal, consumer=worker_id)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        ejecutar_ciclo_despacho,
        "interval",
        seconds=settings.NOTIFICACIONES_INTERVALO_DESPACHO_SEGUNDOS,
        kwargs={"session_factory": AsyncSessionLocal, "worker_id": worker_id},
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        recuperar_pendientes_stream,
        "interval",
        seconds=30,
        args=[redis, AsyncSessionLocal],
        kwargs={"consumer": worker_id, "min_idle_ms": 15000},
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    try:
        while not detener.is_set():
            procesados = await consumir_lote_stream(
                redis,
                AsyncSessionLocal,
                consumer=worker_id,
                block_ms=1000,
            )
            if procesados > 0:
                await ejecutar_ciclo_despacho(
                    session_factory=AsyncSessionLocal,
                    worker_id=worker_id,
                )
    finally:
        scheduler.shutdown(wait=False)
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
