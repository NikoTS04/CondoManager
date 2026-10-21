"""Registro persistente e idempotente de notificaciones (CON-32/34/36).

El registro ocurre en la transacción del consumidor; el envío lo realiza
después el despachador de CON-37 (`entrega.py`). Nunca se envía dentro de esta
transacción, de modo que un rollback no deja mensajes enviados sin registro.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.notificaciones.models import EventoConsumido, Notificacion
from src.modules.notificaciones.templates import PlantillasService


@dataclass(frozen=True)
class NuevaNotificacion:
    condominio_id: uuid.UUID
    evento_id: uuid.UUID
    tipo_evento: str
    plantilla: str
    origen_tipo: str
    origen_id: uuid.UUID
    clave_deduplicacion: str
    destinatario: str
    contexto: dict = field(default_factory=dict)
    canal: str = "EMAIL"
    departamento_id: uuid.UUID | None = None
    usuario_id: uuid.UUID | None = None


async def registrar_notificacion(
    session: AsyncSession, nueva: NuevaNotificacion, ahora: datetime | None = None
) -> uuid.UUID | None:
    """Inserta la notificación en `EN_COLA`; devuelve None si la entrega lógica ya existía."""
    ahora = ahora or datetime.now(UTC)
    asunto, cuerpo = PlantillasService.renderizar(nueva.plantilla, nueva.contexto)
    nuevo_id = uuid.uuid4()
    resultado = await session.execute(
        insert(Notificacion)
        .values(
            id=nuevo_id,
            condominio_id=nueva.condominio_id,
            departamento_id=nueva.departamento_id,
            usuario_id=nueva.usuario_id,
            evento_id=nueva.evento_id,
            tipo_evento=nueva.tipo_evento,
            plantilla=nueva.plantilla,
            origen_tipo=nueva.origen_tipo,
            origen_id=nueva.origen_id,
            clave_deduplicacion=nueva.clave_deduplicacion,
            canal=nueva.canal,
            destinatario=nueva.destinatario,
            asunto=asunto,
            cuerpo=cuerpo,
            contexto=nueva.contexto,
            estado="EN_COLA",
            intentos=0,
            proximo_intento_en=ahora,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        .on_conflict_do_nothing(constraint="uq_notificacion_entrega_logica")
        .returning(Notificacion.id)
    )
    return resultado.scalar_one_or_none()


async def marcar_evento_consumido(
    session: AsyncSession, consumidor: str, event_id: uuid.UUID, event_type: str
) -> bool:
    """Reserva el evento para este consumidor; False si ya fue procesado (reentrega)."""
    resultado = await session.execute(
        insert(EventoConsumido)
        .values(consumidor=consumidor, event_id=event_id, event_type=event_type)
        .on_conflict_do_nothing(constraint="pk_eventos_consumidos")
        .returning(EventoConsumido.event_id)
    )
    return resultado.scalar_one_or_none() is not None


async def cerrar_evento_consumido(
    session: AsyncSession, consumidor: str, event_id: uuid.UUID, creadas: int
) -> None:
    evento = await session.scalar(
        select(EventoConsumido).where(
            EventoConsumido.consumidor == consumidor, EventoConsumido.event_id == event_id
        )
    )
    if evento is not None:
        evento.notificaciones_creadas = creadas
