"""Ejecución Hobby diaria, sin procesos permanentes ni entrega de correo ficticia."""

import asyncio
import os
import secrets

from fastapi import APIRouter, Header, Response
from sqlalchemy import text

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.errors import APIError
from src.modules.cuotas.worker import emitir_pendientes
from src.modules.notificaciones.worker import recuperar_eventos
from src.modules.pagos.worker import evaluar_moras_diarias, limpiar_pendientes

router = APIRouter()


async def ejecutar_diario():
    async with AsyncSessionLocal() as db, db.begin():
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(189560)")):
            raise APIError(409, "JOB_EN_CURSO", "Ya existe una ejecución diaria.")
        await emitir_pendientes(estricto=True)
        await evaluar_moras_diarias(estricto=True)
        await recuperar_eventos()
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
