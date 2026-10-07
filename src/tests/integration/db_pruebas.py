"""Utilidades de base de datos para las pruebas de integración de Reservas y Condominios.

Requiere PostgreSQL levantado (`docker compose up db`). Las filas creadas por cada prueba se
eliminan al final para no ensuciar la base de desarrollo.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import delete, select


def _solo_uuid(valor: str) -> bool:
    try:
        uuid.UUID(valor)
    except ValueError:
        return False
    return True


async def _borrar_condominio(condominio_id: str) -> None:
    from src.core.database import AsyncSessionLocal
    from src.modules.condominios.models import Condominio
    from src.modules.reservas.models import AreaComun, Reserva

    async with AsyncSessionLocal() as session:
        id_condo = uuid.UUID(condominio_id)
        areas = (await session.scalars(
            select(AreaComun.id).where(AreaComun.condominio_id == id_condo)
        )).all()
        if areas:
            await session.execute(delete(Reserva).where(Reserva.area_id.in_(areas)))
        await session.execute(delete(Condominio).where(Condominio.id == id_condo))
        await session.commit()


def borrar_condominio(condominio_id: str) -> None:
    """Elimina el condominio de prueba y todo lo que cuelga de él (cascada)."""
    if not _solo_uuid(condominio_id):
        return
    asyncio.run(_borrar_condominio(condominio_id))


def crear_condominio_de_prueba(client, sufijo: str) -> dict:
    """Alta de un condominio mínimo; si la BD no está disponible, la prueba se omite."""
    try:
        respuesta = client.post(
            "/api/v1/condominio/crear",
            json={
                "nombre": f"Condominio Pruebas {sufijo}",
                "direccion": "Av. Pruebas 000, Lima",
                "moneda": "PEN",
                "regla_mora_tipo": "MONTO_FIJO",
                "monto_mora_fijo": "20.00",
            },
        )
    except Exception as exc:  # pragma: no cover - depende del entorno
        pytest.skip(f"PostgreSQL no disponible para pruebas de integración: {exc}")

    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()
