"""Catálogo demo explícito y conservador: python -m scripts.seed_areas_demo."""

import asyncio
from datetime import time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from scripts.seed_condominio_piloto import generar_datos_areas_comunes
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Condominio
from src.modules.reservas.areas.models import AreaComun
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID


def areas_demo():
    return [
        dict(
            id=UUID(f"11111111-1111-1111-1111-11111111110{index}"),
            condominio_id=CONDOMINIO_PILOTO_ID,
            edificio_id=None,
            nombre=datos["nombre"],
            descripcion=datos.get("descripcion"),
            aforo_maximo=datos["aforo_maximo"],
            costo_reserva=Decimal(str(datos["costo_reserva"])),
            tiempo_maximo_horas=4,
            esta_activa=True,
            hora_apertura=time(0),
            hora_cierre=time(23, 59),
        )
        for index, datos in enumerate(generar_datos_areas_comunes(), 1)
    ]


async def cargar_areas_demo(session):
    contexto = await session.scalar(
        select(Condominio).where(Condominio.id == CONDOMINIO_PILOTO_ID).with_for_update()
    )
    if contexto is None:
        raise RuntimeError("Prepare primero el condominio demo con scripts.seed_usuarios_demo.")
    creadas = 0
    for datos in areas_demo():
        existente = await session.get(AreaComun, datos["id"])
        if existente is not None:
            if existente.condominio_id != CONDOMINIO_PILOTO_ID:
                raise RuntimeError(
                    "Un UUID de área demo pertenece a otro condominio; no se reasigna."
                )
            continue
        session.add(AreaComun(**datos))
        creadas += 1
    await session.flush()
    return creadas


async def main():
    async with AsyncSessionLocal() as session, session.begin():
        creadas = await cargar_areas_demo(session)
    print(f"Áreas demo persistidas. Nuevas: {creadas}; condiciones existentes conservadas.")


if __name__ == "__main__":
    asyncio.run(main())
