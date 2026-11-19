"""Filtros combinados sobre el productor y PostgreSQL reales."""

import pytest

from src.tests.pagos_db import did
from src.tests.pagos_sprint3 import reportar
from src.tests.pagos_sprint3 import sistema as sistema

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def test_filtros_y_paginas_reales(sistema):
    client, _, _, residente, junta = sistema
    primero = await reportar(client, residente, fecha="2026-10-10")
    segundo = await reportar(client, residente, fecha="2026-10-11")
    params = {
        "fecha_desde": "2026-10-10",
        "fecha_hasta": "2026-10-10",
        "banco": "bcp",
        "departamento_id": str(did("102")),
        "estado": "EN_REVISION",
        "limit": 1,
    }
    response = await client.get("/api/v1/pagos/comprobantes", headers=junta, params=params)
    assert response.status_code == 200, response.text
    assert [r["id"] for r in response.json()] == [primero]
    params["offset"] = 1
    assert (
        await client.get("/api/v1/pagos/comprobantes", headers=junta, params=params)
    ).json() == []
    params.update(fecha_hasta="2026-10-11", offset=0, limit=2)
    response = await client.get("/api/v1/pagos/comprobantes", headers=residente, params=params)
    assert {r["id"] for r in response.json()} == {primero, segundo}
