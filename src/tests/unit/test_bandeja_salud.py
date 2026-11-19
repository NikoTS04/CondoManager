"""Lecturas: validación HTTP, filtros SQL antes de paginar y readiness sin secretos."""

from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from src.core import health
from src.core.security import get_current_user
from src.main import app
from src.modules.pagos.persistencia import PagosPersistentesService, get_pagos_service


@pytest.mark.parametrize("fallo", [None, "postgres", "redis", "timeout"])
def test_readiness_no_expone_errores(monkeypatch, fallo):
    postgres = AsyncMock()
    redis = AsyncMock()
    if fallo == "postgres":
        postgres.side_effect = RuntimeError("postgresql://usuario:secreto@servidor")
    elif fallo == "redis":
        redis.side_effect = ConnectionError("redis://secreto")
    elif fallo == "timeout":
        postgres.side_effect = TimeoutError("secreto")
    monkeypatch.setattr(health, "comprobar_postgres", postgres)
    monkeypatch.setattr(health, "comprobar_redis", redis)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == (503 if fallo else 200)
        assert response.json()["dependencies"] == {
            "postgres": "error" if fallo in ("postgres", "timeout") else "ok",
            "redis": "error" if fallo == "redis" else "ok",
        }
        assert "secreto" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/health").status_code == 200
    postgres.assert_awaited_once()
    redis.assert_awaited_once()


@pytest.mark.asyncio
async def test_readiness_timeout_cancela_comprobacion(monkeypatch):
    import asyncio

    original = asyncio.wait_for
    monkeypatch.setattr(health.asyncio, "wait_for", lambda task, timeout: original(task, 0.001))
    cancelled = asyncio.Event()

    async def bloqueada():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    assert await health.estado_dependencia(bloqueada) == "error"
    assert cancelled.is_set()


@pytest.fixture
def bandeja():
    service = AsyncMock()
    service.listar.return_value = []
    app.dependency_overrides[get_current_user] = lambda: {"rol": "ADMIN_JUNTA"}
    app.dependency_overrides[get_pagos_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client, service
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_pagos_service, None)


@pytest.mark.parametrize(
    "params",
    [
        {"fecha_desde": "2026-11-20", "fecha_hasta": "2026-11-01"},
        {"estado": "CONCILIADO"},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"departamento_id": "otro"},
        {"banco": "   "},
        {"fecha_desde": "no-fecha"},
    ],
)
def test_filtros_invalidos_no_consultan(bandeja, params):
    client, service = bandeja
    assert client.get("/api/v1/pagos/comprobantes", params=params).status_code == 422
    service.listar.assert_not_awaited()


def test_bandeja_compatible_y_filtros(bandeja):
    client, service = bandeja
    response = client.get("/api/v1/pagos/comprobantes")
    assert response.status_code == 200 and response.json() == []
    assert response.headers["cache-control"] == "private, no-store"
    assert service.listar.await_count == 1
    assert service.listar.call_args.kwargs["limit"] == 50
    response = client.get(
        "/api/v1/pagos/comprobantes",
        params={
            "fecha_desde": "2026-11-01",
            "fecha_hasta": "2026-11-01",
            "banco": " bcp ",
            "estado": "EN_REVISION",
            "limit": 26,
            "offset": 25,
        },
    )
    assert response.status_code == 200
    assert service.listar.call_args.kwargs == {
        "condominio_id": None,
        "departamento_id": None,
        "fecha_desde": date(2026, 11, 1),
        "fecha_hasta": date(2026, 11, 1),
        "banco": "bcp",
        "estado": "EN_REVISION",
        "limit": 26,
        "offset": 25,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("con_vinculo", [True, False])
async def test_autorizacion_sql_antes_de_paginar(con_vinculo):
    cid, did = uuid4(), uuid4()

    class Session:
        @asynccontextmanager
        async def begin(self):
            yield

        async def scalars(self, query):
            self.query = query
            return []

    session = Session()
    usuario = {
        "rol": "RESIDENTE",
        "condominio_id": str(cid),
        "departamentos": [{"departamento_id": str(did), "es_activo": con_vinculo}],
    }
    assert (
        await PagosPersistentesService(session).listar(
            usuario,
            fecha_desde=date(2026, 11, 1),
            fecha_hasta=date(2026, 11, 30),
            departamento_id=did,
            banco="BCP",
            estado="APROBADO",
            limit=25,
            offset=25,
        )
        == []
    )
    if not con_vinculo:
        assert not hasattr(session, "query")
        return
    query = session.query
    sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert str(cid) in sql and "edificios.condominio_id =" in sql
    assert f"comprobantes_pago.departamento_id = '{did}'" in sql
    assert "lower(comprobantes_pago.banco_origen) = 'bcp'" in sql
    assert "fecha_operacion >= '2026-11-01'" in sql
    assert "fecha_operacion <= '2026-11-30'" in sql
    assert "estado = 'APROBADO'" in sql
    assert sql.index("WHERE") < sql.index("LIMIT 25 OFFSET 25")
