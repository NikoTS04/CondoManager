import os
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("autorizacion_aislada", "finanzas_contrato")

try:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    client = None


def auth():
    from src.core.security import create_access_token
    from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID

    return {
        "Authorization": "Bearer "
        + create_access_token(
            {
                "sub": "prueba-api",
                "rol": "ADMIN_JUNTA",
                "condominio_id": str(CONDOMINIO_PILOTO_ID),
            }
        )
    }


@pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)
def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)
def test_api_emitir_lote_cuotas():
    payload = {
        "condominio_id": str(uuid.uuid4()),
        "periodo": "2026-11",
        "presupuesto_total": "20850.00",
        "fecha_vencimiento": "2026-11-20",
    }
    response = client.post("/api/v1/cuotas/emitir-lote", json=payload)
    # El emisor consume ahora el padrón persistente de CON-3 y exige contexto autenticado.
    # El conteo activo y la idempotencia por condominio se verifican con PostgreSQL real.
    assert response.status_code == 401


@pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)
def test_api_reportar_pago_e_idempotencia():
    from src.modules.usuarios.piloto import vinculo_piloto

    client = TestClient(app, headers=auth())
    payload = {
        "departamento_id": vinculo_piloto("102", "PROPIETARIO_TITULAR")["departamento_id"],
        "banco": "YAPE",
        "numero_operacion": "99881122",
        "fecha_operacion": "2026-10-15",
        "monto": "150.00",
    }
    # 1. Primer reporte
    files = {"archivo_voucher": ("voucher.png", b"doble-explicito", "image/png")}
    res1 = client.post("/api/v1/pagos/reportar", data=payload, files=files)
    assert res1.status_code == 202
    data1 = res1.json()
    assert data1["estado"] == "EN_REVISION"
    assert "idempotency_hash" in data1

    # 2. Reporte duplicado en revisión -> retorna el mismo comprobante sin duplicar
    res2 = client.post("/api/v1/pagos/reportar", data=payload, files=files)
    assert res2.status_code == 200
    assert res2.json()["comprobante_id"] == data1["comprobante_id"]


@pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)
def test_api_reservas_flujo_completo(monkeypatch, autorizacion_aislada):
    from src.tests import reservas_contrato as reservas_router

    client = TestClient(app, headers=auth())

    # Aislar el calendario para que la prueba sea repetible y usar UUID,
    # tal como exige OpenAPI; "402" era rechazado por Pydantic antes del servicio.
    monkeypatch.setattr(reservas_router, "RESERVAS_REGISTRADAS", {})
    departamentos = {d["numero"]: str(d["id"]) for d in autorizacion_aislada.datos.values()}
    condominio_id = str(next(iter(autorizacion_aislada.datos.values()))["condominio_id"])
    # 1. Catálogo de áreas comunes
    res_areas = client.get("/api/v1/areas")
    assert res_areas.status_code == 200
    areas = res_areas.json()
    assert len(areas) >= 4
    area_parrilla = next(a for a in areas if "Parrilla 1" in a["nombre"])
    area_id = area_parrilla["id"]

    # 2. Intento de reserva por dpto moroso (402) -> 403 Forbidden
    payload_moroso = {
        "condominio_id": condominio_id,
        "area_id": area_id,
        "departamento_id": departamentos["402"],
        "fecha_reserva": "2026-10-25",
        "hora_inicio": "19:00",
        "hora_fin": "22:00",
    }
    res_moroso = client.post("/api/v1/reservas", json=payload_moroso)
    assert res_moroso.status_code == 403
    assert res_moroso.json()["error_code"] == "DEUDA_MORA_ACTIVA"

    # 3. Reserva exitosa por residente solvente (102) -> 201 Created
    payload_solvente = {
        "condominio_id": condominio_id,
        "area_id": area_id,
        "departamento_id": departamentos["102"],
        "fecha_reserva": "2026-10-25",
        "hora_inicio": "19:00",
        "hora_fin": "22:00",
    }
    res_solvente = client.post("/api/v1/reservas", json=payload_solvente)
    assert res_solvente.status_code == 201
    reserva_creada = res_solvente.json()
    assert reserva_creada["estado"] == "CONFIRMADA"
    reserva_id = reserva_creada["id"]

    # 4. Conflicto de horario: Otro residente intenta el mismo horario -> 409 Conflict
    payload_conflicto = {
        "condominio_id": condominio_id,
        "area_id": area_id,
        "departamento_id": departamentos["104"],
        "fecha_reserva": "2026-10-25",
        "hora_inicio": "20:00",
        "hora_fin": "23:00",
    }
    res_conflicto = client.post("/api/v1/reservas", json=payload_conflicto)
    assert res_conflicto.status_code == 409
    assert res_conflicto.json()["error_code"] == "HORARIO_NO_DISPONIBLE"

    # 5. Cancelación por administración -> 200 OK
    res_cancelar = client.post(
        f"/api/v1/reservas/{reserva_id}/cancelar",
        json={"motivo": "Fumigación de la terraza", "es_admin": True},
    )
    assert res_cancelar.status_code == 200
    assert res_cancelar.json()["estado"] == "CANCELADA"


@pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)
def test_api_notificaciones_endpoints():
    from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, vinculo_piloto

    client = TestClient(app, headers=auth())
    depto_id = vinculo_piloto("105", "PROPIETARIO_TITULAR")["departamento_id"]
    # 1. Despacho individual
    payload_despacho = {
        "condominio_id": str(CONDOMINIO_PILOTO_ID),
        "departamento_id": depto_id,
        "tipo_evento": "NOTIF_PAGO_CONCILIADO",
        "canal": "EMAIL",
        "destinatario": "residente105@gmail.com",
        "contexto": {
            "nombre": "María Flores",
            "dpto": "105",
            "monto_abonado": "150.00",
            "saldo_restante": "0.00",
        },
    }
    res_despacho = client.post("/api/v1/notificaciones/despachar", json=payload_despacho)
    assert res_despacho.status_code == 202
    log_id = res_despacho.json()["id"]

    # 2. Consulta de logs
    res_logs = client.get("/api/v1/notificaciones/logs", params={"departamento_id": depto_id})
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert len(logs) >= 1
    assert logs[0]["id"] == log_id

    # 3. Reenvío manual
    res_reenviar = client.post(
        f"/api/v1/notificaciones/reenviar/{log_id}",
        json={"nuevo_destinatario": "nuevo_residente105@gmail.com"},
    )
    assert res_reenviar.status_code == 200
    # Un aviso ya en cola se reutiliza; no se cambia el contacto ni se duplica el envío.
    assert res_reenviar.json()["destinatario"] == payload_despacho["destinatario"]

    # 4. Comunicado masivo
    payload_masivo = {
        "condominio_id": str(CONDOMINIO_PILOTO_ID),
        "titulo": "Asamblea General de Propietarios",
        "mensaje": "Se convoca a la asamblea anual ordinaria para el próximo mes.",
        "canal": "EMAIL",
        "remitente": "Junta Directiva",
    }
    res_masivo = client.post("/api/v1/notificaciones/comunicado-masivo", json=payload_masivo)
    assert res_masivo.status_code == 202
    data_masivo = res_masivo.json()
    assert data_masivo["generadas"] == 0
    assert data_masivo["estado_general"] == "EN_COLA"


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_api_condominio_persistencia_postgres(monkeypatch):
    """Verifica HTTP, repositorio y auditoría sobre el esquema migrado, sin create_all."""
    database_url = os.environ.get("CON13_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Defina CON13_TEST_DATABASE_URL para probar PostgreSQL real")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.core.database import get_db_session
    from src.core.models_audit import AuditoriaLogORM
    from src.core.security import create_access_token

    engine = create_async_engine(database_url)
    actor_id = str(uuid.uuid4())
    token = create_access_token({"sub": actor_id, "rol": "SUPERADMIN"})
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:

                    async def test_session():
                        yield session

                    monkeypatch.setitem(app.dependency_overrides, get_db_session, test_session)
                    async with AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as postgres_client:
                        response = await postgres_client.post(
                            "/api/v1/condominios",
                            json={
                                "nombre": "Condominio CI PostgreSQL",
                                "direccion": "Dirección de prueba",
                                "moneda": "PEN",
                                "regla_mora_tipo": "MONTO_FIJO",
                                "monto_mora_fijo": "20.00",
                                "dia_vencimiento": 20,
                                "dias_gracia": 2,
                            },
                        )
                        assert response.status_code == 201, response.text
                        creado = response.json()
                        consulta = await postgres_client.get(f"/api/v1/condominios/{creado['id']}")
                        assert consulta.status_code == 200
                        assert consulta.json() == creado
                        auditoria = (
                            await session.execute(
                                select(AuditoriaLogORM).where(
                                    AuditoriaLogORM.condominio_id == uuid.UUID(creado["id"])
                                )
                            )
                        ).scalar_one()
                        assert auditoria.accion_ejecutada == "CONDOMINIO_CREADO"
                        assert auditoria.actor_id == actor_id
                        assert len(auditoria.hash_actual) == 64
            finally:
                # El servicio sólo hace flush: no dejar datos de prueba en el servicio CI.
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()
