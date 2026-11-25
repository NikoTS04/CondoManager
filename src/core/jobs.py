"""Ejecución Hobby diaria, sin procesos permanentes ni entrega de correo ficticia."""

import asyncio
import os
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Header, Response
from sqlalchemy import text

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.errors import APIError
from src.modules.alertas_contratos.service import evaluar_contratos
from src.modules.cuotas.worker import emitir_pendientes
from src.modules.notificaciones.worker import recuperar_eventos
from src.modules.pagos.worker import evaluar_moras_diarias, limpiar_pendientes

router = APIRouter()


async def registrar_job(estado):
    from sqlalchemy.dialects.postgresql import insert

    from src.modules.notificaciones.models import EstadoJobNotificaciones

    ahora = datetime.now(UTC)
    async with AsyncSessionLocal() as db, db.begin():
        if estado == "EN_CURSO":
            await db.execute(insert(EstadoJobNotificaciones).values(
                nombre="correo", inicio=ahora, fin=None, estado=estado,
            ).on_conflict_do_update(
                index_elements=["nombre"], set_={"inicio": ahora, "fin": None, "estado": estado},
            ))
        else:
            from sqlalchemy import update
            await db.execute(update(EstadoJobNotificaciones).where(
                EstadoJobNotificaciones.nombre == "correo"
            ).values(fin=ahora, estado=estado))


async def ejecutar_notificaciones():
    from src.modules.notificaciones.recordatorios import generar_recordatorios
    from src.modules.notificaciones.worker import procesar_uno, recuperar_inciertos

    if not settings.MAILJET_ENABLED:
        return {"estado": "DESHABILITADO", "procesadas": 0}
    async with AsyncSessionLocal() as db, db.begin():
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(189561)")):
            raise APIError(409, "JOB_EN_CURSO", "Ya existe una ejecución de notificaciones.")
        await registrar_job("EN_CURSO")
        try:
            await recuperar_inciertos()
            await recuperar_eventos()
            await generar_recordatorios()
            procesadas = 0
            for _ in range(20):
                if not await procesar_uno(solo_proveedor=True):
                    break
                procesadas += 1
        except BaseException:
            await registrar_job("INCOMPLETO")
            raise
        await registrar_job("COMPLETADO")
        return {"estado": "COMPLETADO", "procesadas": procesadas}


@router.post("/jobs/notificaciones", tags=["Sistema"])
async def notificaciones(response: Response, authorization: str | None = Header(None)):
    secreto = settings.CRON_SECRET.get_secret_value()
    if not secreto or not secrets.compare_digest(
        (authorization or "").encode(), f"Bearer {secreto}".encode()
    ):
        raise APIError(401, "CRON_NO_AUTORIZADO", "Se requiere credencial del programador.")
    if os.getenv("VERCEL_ENV") == "preview":
        raise APIError(403, "CRON_PREVIEW_DENEGADO", "Preview no ejecuta procesos productivos.")
    try:
        resultado = await asyncio.wait_for(ejecutar_notificaciones(), timeout=45)
    except APIError:
        raise
    except Exception:
        raise APIError(503, "JOB_INCOMPLETO", "Cola pendiente de recuperación.") from None
    response.headers["Cache-Control"] = "no-store"
    return resultado


async def ejecutar_diario():
    async with AsyncSessionLocal() as db, db.begin():
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(189560)")):
            raise APIError(409, "JOB_EN_CURSO", "Ya existe una ejecución diaria.")
        await emitir_pendientes(estricto=True)
        await evaluar_moras_diarias(estricto=True)
        await recuperar_eventos()
        await evaluar_contratos(estricto=True)
        await limpiar_pendientes()


@router.get("/jobs/diario", tags=["Sistema"])
async def diario(response: Response, authorization: str | None = Header(None)):
    secreto = settings.CRON_SECRET.get_secret_value()
    if not secreto or not secrets.compare_digest(
        (authorization or "").encode(), f"Bearer {secreto}".encode()
    ):
        raise APIError(401, "CRON_NO_AUTORIZADO", "Se requiere credencial del programador.")
    if os.getenv("VERCEL_ENV") == "preview":
        raise APIError(403, "CRON_PREVIEW_DENEGADO", "Preview no ejecuta procesos diarios.")
    try:
        await asyncio.wait_for(ejecutar_diario(), timeout=240)
    except APIError:
        raise
    except Exception:
        raise APIError(503, "JOB_INCOMPLETO", "Ejecución incompleta; requiere reintento.") from None
    response.headers["Cache-Control"] = "no-store"
    return {"estado": "COMPLETADO", "correo_enviado": False}
