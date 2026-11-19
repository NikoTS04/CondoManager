"""CON-81: disponibilidad PostgreSQL y compatibilidad del esquema, sin mutaciones."""

import asyncio
from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from asyncpg import PostgresError
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import Base, get_db_session
from src.core.errors import ErrorResponse

router = APIRouter(tags=["Sistema"])


@lru_cache
def revisiones_esperadas():
    return sorted(ScriptDirectory(str(Path(__file__).resolve().parents[2] / "migrations")).get_heads())


async def verificar_esquema(session):
    revisiones = sorted(await session.scalars(text("SELECT version_num FROM alembic_version")))
    if len(revisiones) != 1 or revisiones != revisiones_esperadas():
        raise ValueError("Revisión incompatible")
    esperadas = {
        (tabla.name, columna.name)
        for tabla in Base.metadata.tables.values()
        for columna in tabla.columns
    }
    columnas = await session.execute(
        text(
            """
            SELECT c.relname, a.attname
            FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE c.oid = ANY(CAST(:tablas AS regclass[]))
              AND a.attnum > 0 AND NOT a.attisdropped
            """
        ),
        {"tablas": sorted({tabla for tabla, _ in esperadas})},
    )
    if not esperadas <= set(columnas):
        raise ValueError("Esquema incompleto")
    return revisiones


@router.get("/ready", responses={503: {"model": ErrorResponse}})
@router.get("/api/v1/ready", responses={503: {"model": ErrorResponse}})
async def readiness(response: Response, session: AsyncSession = Depends(get_db_session)):
    response.headers["Cache-Control"] = "no-store"
    try:
        revisiones = await asyncio.wait_for(verificar_esquema(session), timeout=5)
    except (SQLAlchemyError, PostgresError, OSError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            503,
            detail={
                "error_code": "SERVICIO_NO_DISPONIBLE",
                "mensaje": "El servicio no está disponible. Intente más tarde.",
            },
            headers={"Cache-Control": "no-store"},
        ) from exc
    return {"status": "ok", "database": "ok", "schema_revision": revisiones}
