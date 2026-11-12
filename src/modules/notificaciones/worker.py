"""Relay de reservas, consumidor Redis y cola SQL recuperable del prototipo."""

import asyncio
import json
import logging
import random
import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.cuotas.models import EventoLoteOutbox
from src.modules.notificaciones.alertas import crear_alerta
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import EventoConsumido, IntentoNotificacion, Notificacion
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.notificaciones.service import (
    ERRORES_DEFINITIVOS,
    INTERVALOS_REINTENTO_SEGUNDOS,
    NotificacionesService,
)
from src.modules.pagos.models_persistencia import EventoPagoOutbox
from src.modules.reservas.models import EventoReservaOutbox

logger = logging.getLogger(__name__)
STREAM = "condomanager:domain-events"
GRUPO = "notificaciones-v1"


async def recuperar_eventos(session_factory=AsyncSessionLocal):
    """El outbox SQL conserva hechos incluso si Redis pierde un mensaje publicado."""
    for modelo in (EventoLoteOutbox, EventoPagoOutbox, EventoReservaOutbox):
        async with session_factory() as db:
            resuelto = exists().where(
                EventoConsumido.event_id == modelo.id,
                EventoConsumido.consumidor.in_((GRUPO, "notificaciones-descartado-v1")),
            )
            pendientes = (
                await db.execute(
                    select(modelo.id, modelo.payload)
                    .where(~resuelto)
                    .order_by(modelo.id)
                    .limit(100)
                )
            ).all()
        for eid, payload in pendientes:
            resultado = await consumir(session_factory, payload)
            if resultado is None:
                # Solo se descartan copias leídas del outbox, nunca mensajes ajenos del broker.
                async with session_factory() as db, db.begin():
                    await db.execute(
                        insert(EventoConsumido)
                        .values(
                            consumidor="notificaciones-descartado-v1",
                            event_id=eid,
                            procesado_en=datetime.now(UTC),
                        )
                        .on_conflict_do_nothing()
                    )


async def publicar_pendientes(redis, session_factory=AsyncSessionLocal):
    for _ in range(100):
        async with session_factory() as db, db.begin():
            evento = await db.scalar(
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


async def consumir_stream(redis, nombre, session_factory=AsyncSessionLocal):
    try:
        await redis.xgroup_create(STREAM, GRUPO, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    # Recupera también la cola pendiente de consumidores que desaparecieron.
    reclamados = await redis.xautoclaim(STREAM, GRUPO, nombre, 60000, "0-0", count=50)
    mensajes = list(reclamados[1])
    nuevos = await redis.xreadgroup(GRUPO, nombre, {STREAM: ">"}, count=50, block=100)
    for _, lote in nuevos:
        mensajes.extend(lote)
    for mid, campos in mensajes:
        try:
            payload = json.loads(campos.get("event", campos.get(b"event", "null")))
        except (ValueError, TypeError):
            payload = None
        await consumir(session_factory, payload)
        await redis.xack(STREAM, GRUPO, mid)


FALLA_N = re.compile(r"^[^@+]+\+falla(\d+)@", re.IGNORECASE)
REBOTE = re.compile(r"^[^@+]+\+rebote@", re.IGNORECASE)


def transporte_simulado(log, clave):
    """Clave estable: repetir una aceptación local no produce una entrega externa.

    Direcciones `x+fallaN@dominio` fallan (503) mientras `log.intentos <= N`; `x+rebote@dominio`
    responde 550. El contador `intentos` persiste, así que sobrevive a un reinicio del worker.
    """
    destino = log.destinatario or ""
    if REBOTE.match(destino):
        return {"status": 550, "error": "550"}
    falla = FALLA_N.match(destino)
    if falla and log.intentos <= int(falla.group(1)):
        return {"status": 503, "error": "FALLO_TEMPORAL"}
    return {"status": 200, "message_id": f"simulado-{clave}"}


async def procesar_uno(
    session_factory=AsyncSessionLocal,
    transport=transporte_simulado,
    ahora=None,
    jitter=random.randint,
):
    reloj_fijo = ahora
    ahora = ahora or datetime.now(UTC)
    async with session_factory() as db, db.begin():
        pendiente = exists().where(
            IntentoNotificacion.notificacion_id == Notificacion.id,
            IntentoNotificacion.terminado_en.is_(None),
        )
        log = await db.scalar(
            select(Notificacion)
            .where(
                Notificacion.estado.in_(("EN_COLA", "REINTENTANDO")),
                Notificacion.intentos < 4,
                or_(Notificacion.bloqueado_hasta.is_(None), Notificacion.bloqueado_hasta <= ahora),
                or_(
                    Notificacion.proximo_reintento.is_(None),
                    Notificacion.proximo_reintento <= ahora,
                ),
                ~pendiente,
            )
            .order_by(Notificacion.fecha_creacion, Notificacion.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if log is None:
            return False
        destinos = await NotificacionesRepository(db).destinatarios(
            log.condominio_id,
            log.departamento_id,
            log.canal,
        )
        if not any(
            u.id == log.usuario_destinatario_id and c == log.destinatario for u, _, c in destinos
        ):
            log.estado = "FALLIDO_PERMANENTE"
            log.error_mensaje = "DESTINATARIO_REVOCADO_O_CONTACTO_MODIFICADO"
            log.proximo_reintento = None
            await crear_alerta(db, log, "DESTINATARIO_INVALIDO", ahora)
            return True
        # El prototipo no configura un proveedor sin reconciliación idempotente.
        if log.transporte != "SIMULADO":
            log.estado = "FALLIDO_PERMANENTE"
            log.error_mensaje = "PROVEEDOR_NO_CONFIGURADO"
            await crear_alerta(db, log, "PROVEEDOR_NO_CONFIGURADO", ahora)
            return True
        log.intentos += 1
        # Cambiar la fila impide adquirirla desde una instantánea anterior al commit.
        log.bloqueado_hasta = ahora + timedelta(minutes=5)
        intento = IntentoNotificacion(
            id=uuid4(),
            notificacion_id=log.id,
            ciclo=log.ciclo,
            numero=log.intentos,
            iniciado_en=ahora,
        )
        db.add(intento)
        await db.flush()
        iid, lid = intento.id, log.id
        clave = f"{lid}-{log.ciclo}-{log.intentos}"
    # El intento ya es durable antes del efecto externo. No mantener locks de SQL en red.
    try:
        resultado = await asyncio.to_thread(transport, log, clave)
    except Exception:
        resultado = {"status": 500, "error": "FALLO_TRANSPORTE"}
    ahora = reloj_fijo or datetime.now(UTC)
    async with session_factory() as db, db.begin():
        log = await db.scalar(select(Notificacion).where(Notificacion.id == lid).with_for_update())
        intento = await db.get(IntentoNotificacion, iid)
        if intento.terminado_en is not None:
            return True
        intento.terminado_en = ahora
        log.bloqueado_hasta = None
        log.fecha_actualizacion = ahora
        status = resultado.get("status", 500)
        if 200 <= status < 300:
            log.estado = "ENVIADO"
            log.proveedor_message_id = str(resultado.get("message_id") or clave)
            intento.proveedor_message_id = log.proveedor_message_id
            log.proximo_reintento = None
            log.error_mensaje = None
        else:
            # Evitar mensajes del proveedor que puedan incluir contactos o secretos.
            definitivo = NotificacionesService.es_error_definitivo(
                status, str(resultado.get("error", ""))
            )
            definitivo = definitivo or (400 <= status < 500 and status not in (408, 429))
            error = (
                str(status)
                if str(status) in ERRORES_DEFINITIVOS
                else ("FALLO_DEFINITIVO" if definitivo else "FALLO_TEMPORAL")
            )
            intento.error = log.error_mensaje = error
            if definitivo or log.intentos >= 4:
                log.estado = "FALLIDO_PERMANENTE"
                log.proximo_reintento = None
                await crear_alerta(
                    db, log, "ERROR_DEFINITIVO" if definitivo else "INTENTOS_AGOTADOS", ahora
                )
            else:
                segundos = INTERVALOS_REINTENTO_SEGUNDOS[log.intentos]
                if log.intentos == 1:
                    segundos += jitter(-15, 15)
                log.estado = "REINTENTANDO"
                log.proximo_reintento = ahora + timedelta(seconds=segundos)
    return True


async def recuperar_inciertos(session_factory=AsyncSessionLocal, ahora=None):
    ahora = ahora or datetime.now(UTC)
    async with session_factory() as db, db.begin():
        incierto = exists().where(
            IntentoNotificacion.notificacion_id == Notificacion.id,
            IntentoNotificacion.terminado_en.is_(None),
            IntentoNotificacion.iniciado_en < ahora - timedelta(minutes=5),
        )
        logs = list(
            await db.scalars(select(Notificacion).where(incierto).with_for_update(skip_locked=True))
        )
        for log in logs:
            intentos = list(
                await db.scalars(
                    select(IntentoNotificacion)
                    .where(
                        IntentoNotificacion.notificacion_id == log.id,
                        IntentoNotificacion.terminado_en.is_(None),
                    )
                    .with_for_update()
                )
            )
            for intento in intentos:
                intento.terminado_en = ahora
                intento.error = "ACEPTACION_INCIERTA"
            log.estado = "FALLIDO_PERMANENTE"
            log.error_mensaje = "ACEPTACION_INCIERTA_REQUIERE_REVISION"
            log.bloqueado_hasta = None
            log.proximo_reintento = None
            log.fecha_actualizacion = ahora
            await crear_alerta(db, log, "ACEPTACION_INCIERTA", ahora)


async def main():
    logging.basicConfig(level=logging.INFO)
    nombre = str(uuid4())
    redis = Redis.from_url(
        settings.REDIS_URL, decode_responses=True, socket_timeout=10, socket_connect_timeout=10
    )
    try:
        while True:
            try:
                await publicar_pendientes(redis)
                await consumir_stream(redis, nombre)
            except Exception:
                logger.exception("Eventos pendientes: se recuperarán en la próxima pasada.")
            try:
                await recuperar_eventos()
                await recuperar_inciertos()
                for _ in range(100):
                    if not await procesar_uno():
                        break
            except Exception:
                logger.exception("Cola de notificaciones pendiente de recuperación.")
            await asyncio.sleep(5)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
