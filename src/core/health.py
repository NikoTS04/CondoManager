"""Readiness de dependencias; liveness sigue disponible en main."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from src.core.config import settings
from src.core.database import engine

router = APIRouter(tags=["Sistema"])


async def comprobar_postgres():
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def comprobar_redis():
    async with Redis.from_url(
        settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
    ) as redis:
        if not await redis.ping():
            raise ConnectionError("Redis no respondió PONG")


async def estado_dependencia(comprobar):
    try:
        await asyncio.wait_for(comprobar(), timeout=2)
        return "ok"
    except Exception:
        # El diagnóstico público nunca incluye URLs, credenciales ni errores del driver.
        return "error"


async def estado_redis():
    if not settings.REDIS_REQUIRED:
        return "disabled"
    return await estado_dependencia(comprobar_redis)


@router.get("/health/ready")
async def readiness():
    postgres, redis = await asyncio.gather(
        estado_dependencia(comprobar_postgres), estado_redis()
    )
    disponible = postgres == "ok" and redis in ("ok", "disabled")
    return JSONResponse(
        status_code=200 if disponible else 503,
        content={
            "status": "ok" if disponible else "error",
            "dependencies": {"postgres": postgres, "redis": redis},
        },
        headers={"Cache-Control": "no-store"},
    )
