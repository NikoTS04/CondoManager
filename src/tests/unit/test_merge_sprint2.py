"""Regresiones del cruce entre catalogo, portal y solvencia; sin base de datos."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.reservas.persistencia import get_reservas_service
from src.modules.usuarios.departamentos import DepartamentosPortalRepository


def test_catalogo_y_solvencia_comparten_sesion_para_no_bloquearse():
    session = object()
    assert get_reservas_service(SimpleNamespace(session=session)).session is session


def test_grafo_alembic_conserva_ambas_ramas_con_una_cabeza():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_heads() == ["20261021_0013"]
    revisiones = {r.revision for r in scripts.walk_revisions()}
    assert {"20261020_0009", "20261020_0009_pagos", "20261020_0010"} <= revisiones
    assert len(revisiones) == 14


@pytest.mark.asyncio
@pytest.mark.parametrize("dias_vencida, deuda", [(2, "0.00"), (4, "100.00")])
async def test_portal_conserva_edificio_y_calcula_deuda_con_gracia(
    monkeypatch, dias_vencida, deuda
):
    async def cuotas(self, did):
        return [
            SimpleNamespace(
                fecha_vencimiento=datetime.now(UTC).date() - timedelta(days=dias_vencida),
                estado="PENDIENTE",
                monto_total_exigible=Decimal("150.00"),
                monto_pagado=Decimal("50.00"),
            )
        ]

    monkeypatch.setattr(SQLAlchemyPagosRepository, "cuotas", cuotas)
    edificio = SimpleNamespace(id=uuid4(), condominio_id=uuid4(), nombre_bloque="Torre A")
    departamento = SimpleNamespace(
        id=uuid4(),
        numero="102",
        piso=1,
        coeficiente_participacion=Decimal("1.00"),
        saldo_a_favor=Decimal("0.00"),
        estado_financiero="EN_MORA",
        activo=True,
    )
    resultado = await DepartamentosPortalRepository(object())._representar(
        departamento,
        edificio,
        SimpleNamespace(dias_gracia=3),
    )
    assert resultado["edificio_id"] == edificio.id
    assert resultado["edificio_nombre"] == "Torre A"
    assert resultado["deuda_vencida"] == Decimal(deuda)
    assert resultado["estado_financiero"] == ("EN_MORA" if Decimal(deuda) else "AL_DIA")
