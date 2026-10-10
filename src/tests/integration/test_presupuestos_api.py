"""Pruebas del contrato HTTP y reglas de aplicación de CON-9."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.security import create_access_token
from src.main import app
from src.modules.condominios.models import Condominio
from src.modules.cuotas.presupuestos.router import get_presupuesto_repository
from src.modules.cuotas.presupuestos.schemas import CrearPresupuestoRequest
from src.modules.cuotas.presupuestos.service import ActorPresupuesto, PresupuestosService
from src.tests.fakes import FakePresupuestoRepository


def crear_condominio(moneda: str = "PEN", nombre: str = "Villa Bonita 3") -> Condominio:
    return Condominio(
        id=uuid4(),
        nombre=nombre,
        direccion="Av. Principal 123, Lima",
        moneda=moneda,
        regla_mora_tipo="MONTO_FIJO",
        monto_mora_fijo=Decimal("20.00"),
        tasa_mora_porcentaje=None,
        dia_vencimiento=20,
        dias_gracia=2,
        activo=True,
        creado_en=datetime.now(UTC),
    )


@pytest.fixture
def repository() -> FakePresupuestoRepository:
    fake = FakePresupuestoRepository()
    condominio = crear_condominio()
    fake.condominios[condominio.id] = condominio
    app.dependency_overrides[get_presupuesto_repository] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_presupuesto_repository, None)


@pytest.fixture
def condominio(repository: FakePresupuestoRepository) -> Condominio:
    return next(iter(repository.condominios.values()))


@pytest.fixture
def client(repository: FakePresupuestoRepository):
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(
    rol: str,
    condominio_id: UUID | None,
    *,
    subject: str | None = None,
) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": subject or str(uuid4()),
            "email": "usuario@condomanager.pe",
            "rol": rol,
            "condominio_id": str(condominio_id) if condominio_id is not None else None,
            "departamentos": [],
        }
    )
    return {"Authorization": f"Bearer {token}"}


def payload(
    condominio_id: UUID,
    *,
    periodo: str = "2026-10",
    moneda: str = "PEN",
    monto: str = "20000.00",
    vencimiento: str = "2026-10-20",
) -> dict[str, str]:
    return {
        "condominio_id": str(condominio_id),
        "periodo": periodo,
        "moneda": moneda,
        "monto_total": monto,
        "fecha_vencimiento": vencimiento,
    }


def crear_borrador(
    client: TestClient,
    condominio_id: UUID,
    *,
    subject: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/presupuestos",
        json=payload(condominio_id),
        headers=auth_headers("ADMIN_JUNTA", condominio_id, subject=subject),
    )
    assert response.status_code == 201
    return response.json()


def test_admin_crea_actualiza_borrador_y_registra_auditoria(
    client: TestClient,
    repository: FakePresupuestoRepository,
    condominio: Condominio,
):
    actor_id = str(uuid4())
    headers = auth_headers("ADMIN_JUNTA", condominio.id, subject=actor_id)

    creacion = client.post(
        "/api/v1/presupuestos",
        json=payload(condominio.id),
        headers=headers,
    )

    assert creacion.status_code == 201
    creado = creacion.json()
    UUID(creado["id"])
    assert creado["estado"] == "BORRADOR"
    assert creado["creado_por"] == actor_id
    assert creado["monto_total"] == "20000.00"
    assert creado["aprobado_por"] is None
    assert repository.auditorias[-1].accion_ejecutada == "PRESUPUESTO_CREADO"

    actualizacion = client.put(
        f"/api/v1/presupuestos/{creado['id']}",
        json={
            "periodo": "2026-10",
            "moneda": "PEN",
            "monto_total": "20500.00",
            "fecha_vencimiento": "2026-10-20",
        },
        headers=headers,
    )

    assert actualizacion.status_code == 200
    actualizado = actualizacion.json()
    assert actualizado["id"] == creado["id"]
    assert actualizado["monto_total"] == "20500.00"
    auditoria = repository.auditorias[-1]
    assert auditoria.accion_ejecutada == "PRESUPUESTO_MODIFICADO"
    assert auditoria.estado_anterior["monto_total"] == "20000.00"
    assert auditoria.estado_posterior["monto_total"] == "20500.00"


@pytest.mark.parametrize(
    ("cambios", "codigo_esperado"),
    [
        ({"periodo": "2026-13"}, "DATOS_PRESUPUESTO_INVALIDOS"),
        ({"monto_total": "0.00"}, "DATOS_PRESUPUESTO_INVALIDOS"),
        ({"monto_total": 20000}, "DATOS_PRESUPUESTO_INVALIDOS"),
        ({"fecha_vencimiento": "2026-11-20"}, "DATOS_PRESUPUESTO_INVALIDOS"),
        ({"moneda": "USD"}, "DATOS_PRESUPUESTO_INVALIDOS"),
    ],
)
def test_rechaza_datos_invalidos_sin_persistir(
    client: TestClient,
    repository: FakePresupuestoRepository,
    condominio: Condominio,
    cambios: dict[str, object],
    codigo_esperado: str,
):
    datos: dict[str, object] = payload(condominio.id)
    datos.update(cambios)

    response = client.post(
        "/api/v1/presupuestos",
        json=datos,
        headers=auth_headers("ADMIN_JUNTA", condominio.id),
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == codigo_esperado
    assert repository.presupuestos == {}
    assert repository.auditorias == []


def test_aprobacion_registra_actor_fecha_y_vuelve_inmutable(
    client: TestClient,
    repository: FakePresupuestoRepository,
    condominio: Condominio,
):
    actor_id = str(uuid4())
    headers = auth_headers("ADMIN_JUNTA", condominio.id, subject=actor_id)
    borrador = crear_borrador(client, condominio.id, subject=actor_id)

    aprobacion = client.post(
        f"/api/v1/presupuestos/{borrador['id']}/aprobar",
        headers=headers,
    )

    assert aprobacion.status_code == 200
    aprobado = aprobacion.json()
    assert aprobado["estado"] == "APROBADO"
    assert aprobado["aprobado_por"] == actor_id
    aprobado_en = datetime.fromisoformat(aprobado["aprobado_en"].replace("Z", "+00:00"))
    assert aprobado_en.utcoffset() == UTC.utcoffset(aprobado_en)
    assert repository.auditorias[-1].accion_ejecutada == "PRESUPUESTO_APROBADO"
    assert UUID(borrador["id"]) in repository.bloqueos_solicitados

    modificacion = client.put(
        f"/api/v1/presupuestos/{borrador['id']}",
        json={
            "periodo": "2026-10",
            "moneda": "PEN",
            "monto_total": "21000.00",
            "fecha_vencimiento": "2026-10-20",
        },
        headers=headers,
    )
    reaprobacion = client.post(
        f"/api/v1/presupuestos/{borrador['id']}/aprobar",
        headers=headers,
    )

    assert modificacion.status_code == 409
    assert modificacion.json()["error_code"] == "PRESUPUESTO_NO_EDITABLE"
    assert reaprobacion.status_code == 409
    assert reaprobacion.json()["error_code"] == "PRESUPUESTO_NO_EDITABLE"


def test_exige_token_y_restringe_al_auditor_a_solo_lectura(
    client: TestClient,
    condominio: Condominio,
):
    sin_token = client.post("/api/v1/presupuestos", json=payload(condominio.id))
    assert sin_token.status_code == 401
    assert sin_token.json()["error_code"] == "NO_AUTENTICADO"

    borrador = crear_borrador(client, condominio.id)
    headers_auditor = auth_headers("AUDITOR", condominio.id)
    consulta = client.get(
        f"/api/v1/condominios/{condominio.id}/presupuestos/2026-10",
        headers=headers_auditor,
    )
    aprobacion = client.post(
        f"/api/v1/presupuestos/{borrador['id']}/aprobar",
        headers=headers_auditor,
    )

    assert consulta.status_code == 200
    assert consulta.json()["id"] == borrador["id"]
    assert aprobacion.status_code == 403
    assert aprobacion.json()["error_code"] == "PRESUPUESTO_ACCESO_DENEGADO"


def test_impide_duplicado_en_un_condominio_y_permite_el_periodo_en_otro(
    client: TestClient,
    repository: FakePresupuestoRepository,
    condominio: Condominio,
):
    headers_admin = auth_headers("ADMIN_JUNTA", condominio.id)
    primero = client.post(
        "/api/v1/presupuestos",
        json=payload(condominio.id),
        headers=headers_admin,
    )
    duplicado = client.post(
        "/api/v1/presupuestos",
        json=payload(condominio.id),
        headers=headers_admin,
    )

    assert primero.status_code == 201
    assert duplicado.status_code == 409
    assert duplicado.json()["error_code"] == "PRESUPUESTO_PERIODO_DUPLICADO"
    assert len(repository.presupuestos) == 1

    otro = crear_condominio(nombre="Condominio Sur")
    repository.condominios[otro.id] = otro
    segundo = client.post(
        "/api/v1/presupuestos",
        json=payload(otro.id),
        headers=auth_headers("SUPERADMIN", None),
    )

    assert segundo.status_code == 201
    assert segundo.json()["id"] != primero.json()["id"]
    assert len(repository.presupuestos) == 2


def test_aisla_consulta_entre_condominios(
    client: TestClient,
    repository: FakePresupuestoRepository,
    condominio: Condominio,
):
    borrador = crear_borrador(client, condominio.id)
    otro = crear_condominio(nombre="Condominio Sur")
    repository.condominios[otro.id] = otro

    response = client.get(
        f"/api/v1/condominios/{condominio.id}/presupuestos/2026-10",
        headers=auth_headers("ADMIN_JUNTA", otro.id),
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "PRESUPUESTO_ACCESO_DENEGADO"
    assert borrador["monto_total"] not in response.text


@pytest.mark.asyncio
async def test_con11_solo_recupera_presupuesto_aprobado():
    repository = FakePresupuestoRepository()
    condominio = crear_condominio()
    repository.condominios[condominio.id] = condominio
    service = PresupuestosService(repository)
    actor = ActorPresupuesto(
        id=str(uuid4()),
        rol="ADMIN_JUNTA",
        condominio_id=condominio.id,
    )
    request = CrearPresupuestoRequest(
        condominio_id=condominio.id,
        periodo="2026-10",
        moneda="PEN",
        monto_total="20000.00",
        fecha_vencimiento=date(2026, 10, 20),
    )

    borrador = await service.crear(request, actor)
    assert await service.obtener_aprobado_para_emision(condominio.id, "2026-10") is None

    await service.aprobar(borrador.id, actor)
    utilizable = await service.obtener_aprobado_para_emision(condominio.id, "2026-10")

    assert utilizable is not None
    assert utilizable.id == borrador.id
    assert utilizable.monto_total == Decimal("20000.00")
    assert utilizable.fecha_vencimiento == date(2026, 10, 20)
