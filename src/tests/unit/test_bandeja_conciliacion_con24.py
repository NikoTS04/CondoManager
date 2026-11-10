"""Pruebas unitarias de CON-24: Consultar la bandeja de conciliación con filtros y paginación."""

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.errors import APIError, api_error_handler
from src.core.security import get_current_user
from src.modules.pagos.persistencia import get_pagos_service
from src.modules.pagos.router import router
from src.modules.pagos.schemas import ComprobantePagoDTO


class MockPagosService:
    def __init__(self, comprobantes=None):
        self.comprobantes = comprobantes or []
        self.llamada_listar = {}

    async def listar(
        self,
        usuario,
        condominio_id=None,
        fecha_desde=None,
        fecha_hasta=None,
        departamento_id=None,
        banco=None,
        estado=None,
        limit=50,
        offset=0,
    ):
        self.llamada_listar = {
            "usuario": usuario,
            "condominio_id": condominio_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "departamento_id": departamento_id,
            "banco": banco,
            "estado": estado,
            "limit": limit,
            "offset": offset,
        }
        res = list(self.comprobantes)
        if departamento_id:
            res = [c for c in res if c.departamento_id == departamento_id]
        if fecha_desde:
            res = [c for c in res if c.fecha_operacion >= fecha_desde]
        if fecha_hasta:
            res = [c for c in res if c.fecha_operacion <= fecha_hasta]
        if banco:
            res = [c for c in res if c.banco.lower() == banco.strip().lower()]
        if estado:
            res = [c for c in res if c.estado == estado]
        return res[offset : offset + limit]


def app_con_mock(mock_service, usuario_rol="ADMIN_JUNTA", departamentos=None):
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(router, prefix="/api/v1")
    cid = uuid4()
    mock_user = {
        "sub": str(uuid4()),
        "email": "test@condomanager.pe",
        "rol": usuario_rol,
        "condominio_id": str(cid),
        "departamentos": departamentos or [],
    }
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_pagos_service] = lambda: mock_service
    return app, mock_user, cid


def test_validacion_rango_fechas_invalido():
    service = MockPagosService()
    app, _, _ = app_con_mock(service)
    client = TestClient(app)

    response = client.get(
        "/api/v1/pagos/comprobantes?fecha_desde=2026-10-25&fecha_hasta=2026-10-20"
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "RANGO_FECHAS_INVALIDO"


def test_validacion_estado_invalido():
    service = MockPagosService()
    app, _, _ = app_con_mock(service)
    client = TestClient(app)

    response = client.get("/api/v1/pagos/comprobantes?estado=INEXISTENTE")
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "ESTADO_INVALIDO"


def test_filtros_combinables_correctamente_pasados_al_servicio():
    service = MockPagosService()
    app, _, cid = app_con_mock(service)
    client = TestClient(app)

    dep_id = uuid4()
    url = (
        f"/api/v1/pagos/comprobantes?condominio_id={cid}"
        f"&fecha_desde=2026-10-01&fecha_hasta=2026-10-20"
        f"&departamento_id={dep_id}&banco=BCP&estado=EN_REVISION"
        f"&limit=25&offset=10"
    )
    response = client.get(url)
    assert response.status_code == 200

    params = service.llamada_listar
    assert params["fecha_desde"] == date(2026, 10, 1)
    assert params["fecha_hasta"] == date(2026, 10, 20)
    assert params["departamento_id"] == dep_id
    assert params["banco"] == "BCP"
    assert params["estado"] == "EN_REVISION"
    assert params["limit"] == 25
    assert params["offset"] == 10


def test_filtrado_en_memoria_y_paginacion():
    dep_a = uuid4()
    comprobantes = [
        ComprobantePagoDTO(
            id=uuid4(),
            departamento_id=dep_a,
            banco="BCP",
            numero_operacion=f"OP-00{i}",
            fecha_operacion=date(2026, 10, 10 + i),
            monto=Decimal("150.00"),
            estado="EN_REVISION" if i % 2 == 0 else "APROBADO",
            idempotency_hash=f"hash_{i}",
            url_voucher=f"/api/v1/pagos/voucher_{i}",
        )
        for i in range(10)
    ]
    service = MockPagosService(comprobantes)
    app, _, _ = app_con_mock(service)
    client = TestClient(app)

    # Filtrar por estado APROBADO
    r = client.get("/api/v1/pagos/comprobantes?estado=APROBADO")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 5
    assert all(item["estado"] == "APROBADO" for item in items)

    # Filtrar con paginación
    r_pag = client.get("/api/v1/pagos/comprobantes?limit=3&offset=0")
    assert r_pag.status_code == 200
    assert len(r_pag.json()) == 3


@pytest.mark.asyncio
async def test_residente_acceso_denegado_departamento_ajeno():
    from src.modules.pagos.persistencia import PagosPersistentesService

    dep_propio = uuid4()
    dep_ajeno = uuid4()
    user_residente = {
        "sub": str(uuid4()),
        "rol": "RESIDENTE",
        "condominio_id": str(uuid4()),
        "departamentos": [{"departamento_id": str(dep_propio), "es_activo": True}],
    }

    class DummySession:
        @asynccontextmanager
        async def begin(self):
            yield self

    service = PagosPersistentesService(DummySession())
    with pytest.raises(APIError) as exc:
        await service.listar(user_residente, departamento_id=dep_ajeno)
    assert exc.value.status_code == 403
    assert exc.value.error_code == "ACCESO_DENEGADO"
