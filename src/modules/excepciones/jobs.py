"""Cola de resoluciones de jobs consumida por la ejecución programada."""

import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.errors import APIError
from src.core.reintentos_job import puede_reintentar_job
from src.modules.excepciones.models import Excepcion, ResolucionExcepcion
from src.modules.excepciones.schemas import Accion, Estado
from src.modules.notificaciones.models import AlertaNotificacion

JOB_NOTIFICACIONES = "notificaciones"
ESTADOS_ACTIVOS = ("EN_COLA", "EN_CURSO")
RESULTADOS: dict[str, Estado] = {
    "EN_COLA": "EN_PROCESO",
    "EN_CURSO": "EN_PROCESO",
    "COMPLETADO": "RESUELTA",
    "FALLIDO": "FALLIDA",
    "INCIERTO": "FALLIDA",
    "OMITIDO": "RESUELTA",
    "PENDIENTE_INFORMACION": "PENDIENTE_INFORMACION",
}
RESULTADO_INICIAL = {
    "REINTENTAR_JOB": "EN_COLA",
    "CERRAR_CON_MOTIVO": "OMITIDO",
    "SOLICITAR_INFORMACION": "PENDIENTE_INFORMACION",
}


def estado_job(alerta: AlertaNotificacion, ultima: ResolucionExcepcion | None = None) -> Estado:
    if alerta.atendida_en is not None:
        return "RESUELTA"
    return ultima.estado if ultima else "ABIERTA"


def acciones_job(alerta: AlertaNotificacion, historial: list[ResolucionExcepcion]) -> list[Accion]:
    estado = estado_job(alerta, historial[0] if historial else None)
    if estado in {"RESUELTA", "EN_PROCESO"}:
        return []
    acciones: list[Accion] = ["CERRAR_CON_MOTIVO"]
    if estado != "PENDIENTE_INFORMACION":
        acciones.append("SOLICITAR_INFORMACION")
    if (
        puede_reintentar_job(alerta.origen_id)
        and settings.MAILJET_ENABLED
        and os.getenv("VERCEL_ENV") != "preview"
        and all(r.accion != "REINTENTAR_JOB" for r in historial)
    ):
        acciones.insert(0, "REINTENTAR_JOB")
    return acciones


def actual_activo(nombre: str):
    return select(ResolucionExcepcion).where(
        ResolucionExcepcion.nombre_job == nombre,
        ResolucionExcepcion.resultado_job.in_(ESTADOS_ACTIVOS),
    )


async def comprobar_cola_job(db: AsyncSession, nombre: str) -> None:
    # Serializa solicitudes de alertas de distintas fechas del mismo job.
    await db.execute(text("SELECT pg_advisory_xact_lock(189562)"))
    if await db.scalar(actual_activo(nombre).with_only_columns(ResolucionExcepcion.id)):
        raise APIError(409, "JOB_REINTENTO_ACTIVO", "La tarea ya tiene un reintento activo.")


async def _registrar_resultado(
    db: AsyncSession, registro: ResolucionExcepcion, resultado: str, ahora: datetime
) -> None:
    registro.resultado_job = resultado
    registro.estado = RESULTADOS[resultado]
    registro.efecto = {**registro.efecto, "estado_operacion": resultado}
    registro.fin_job = ahora
    excepcion = await db.get(Excepcion, registro.excepcion_id)
    if resultado == "COMPLETADO":
        alerta = await db.get(AlertaNotificacion, excepcion.alerta_id, with_for_update=True)
        alerta.atendida_en, alerta.atendida_por = ahora, registro.actor_id
    excepcion.estado = registro.estado


async def tomar_reintento(sesiones) -> UUID | None:
    """Se llama con el bloqueo del job adquirido en la ejecución programada."""
    ahora = datetime.now(UTC)
    async with sesiones() as db, db.begin():
        registro = await db.scalar(actual_activo(JOB_NOTIFICACIONES).with_for_update())
        if registro is None:
            return None
        if registro.resultado_job == "EN_CURSO":
            await _registrar_resultado(db, registro, "INCIERTO", ahora)
            return None
        registro.resultado_job = "EN_CURSO"
        registro.efecto = {**registro.efecto, "estado_operacion": "EN_CURSO"}
        registro.inicio_job = ahora
        return registro.id


async def finalizar_reintento(sesiones, id: UUID | None, resultado: str) -> None:
    if id is None:
        return
    async with sesiones() as db, db.begin():
        registro = await db.get(ResolucionExcepcion, id, with_for_update=True)
        if registro is not None and registro.resultado_job == "EN_CURSO":
            await _registrar_resultado(db, registro, resultado, datetime.now(UTC))
