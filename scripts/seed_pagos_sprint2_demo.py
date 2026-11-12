"""Datos financieros opt-in para el prototipo; nunca se ejecuta al arrancar."""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid5

from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Condominio, Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID


async def preparar_demo(session):
    if not settings.DEMO_MODE:
        raise RuntimeError("Active DEMO_MODE únicamente en un entorno de demostración.")
    cid = CONDOMINIO_PILOTO_ID
    usuario = await session.get(Usuario, id_demo("moroso402@villabonita3.pe"))
    if usuario is None or usuario.email != "moroso402@villabonita3.pe":
        raise RuntimeError(
            "Primero provisione las identidades demo; no se modifican otras cuentas."
        )
    await session.execute(select(Condominio).where(Condominio.id == cid).with_for_update())
    did = uuid5(cid, "402")
    depto = await session.scalar(
        select(Departamento).where(Departamento.id == did).with_for_update()
    )
    if depto is None:
        raise RuntimeError("Falta el departamento demo 402.")
    anterior = datetime.now(UTC).date().replace(day=1) - timedelta(days=1)
    periodo = anterior.strftime("%Y-%m")
    existente = await session.scalar(
        select(CuotaMantenimiento.id).where(
            CuotaMantenimiento.departamento_id == did,
            CuotaMantenimiento.periodo == periodo,
        )
    )
    if existente is not None:
        return False
    session.add(
        CuotaMantenimiento(
            id=uuid5(cid, f"cuota-demo-sprint2:{periodo}"),
            departamento_id=did,
            periodo=periodo,
            monto_ordinario=Decimal("150.00"),
            monto_extraordinario=Decimal("0.00"),
            monto_mora=Decimal("20.00"),
            monto_descuento=Decimal("0.00"),
            monto_total_exigible=Decimal("170.00"),
            monto_pagado=Decimal("0.00"),
            fecha_emision=anterior.replace(day=1),
            fecha_vencimiento=anterior.replace(day=20),
            estado="EN_MORA",
        )
    )
    previo = depto.estado_financiero
    depto.estado_financiero = "EN_MORA"
    await SQLAlchemyPagosRepository(session).auditar(
        {"rol": "SISTEMA_AUTOMATICO", "sub": "SEED_DEMO_CON70"},
        cid,
        did,
        "CUOTA_DEMO_SPRINT2_CREADA",
        "PROVISION_EXPLICITA_ENTORNO_DEMO",
        {"estado_financiero": previo},
        {"periodo": periodo, "deuda_demo": "170.00", "estado_financiero": "EN_MORA"},
    )
    return True


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmar-datos-demo", action="store_true", required=True)
    parser.parse_args()
    async with AsyncSessionLocal() as session, session.begin():
        creada = await preparar_demo(session)
    print(
        "Cuota demo de S/ 170.00 creada para 402."
        if creada
        else "Cuota existente conservada; no se modificaron datos."
    )


if __name__ == "__main__":
    asyncio.run(main())
