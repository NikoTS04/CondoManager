from decimal import Decimal
import uuid
import pytest

try:
    from fastapi.testclient import TestClient
    from src.main import app
    client = TestClient(app)
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    client = None


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual")
def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual")
def test_api_emitir_lote_cuotas():
    payload = {
        "condominio_id": str(uuid.uuid4()),
        "periodo": "2026-11",
        "presupuesto_total": "20850.00",
        "fecha_vencimiento": "2026-11-20",
    }
    response = client.post("/api/v1/cuotas/emitir-lote", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["periodo"] == "2026-11"
    assert data["total_cuotas_emitidas"] == 139
    assert Decimal(data["monto_total_facturado"]) == Decimal("20850.00")

    # Intentar emitir el mismo periodo de nuevo debe dar 409 Conflict
    response_dup = client.post("/api/v1/cuotas/emitir-lote", json=payload)
    assert response_dup.status_code == 409


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual")
def test_api_reportar_pago_e_idempotencia():
    payload = {
        "departamento_id": str(uuid.uuid4()),
        "banco": "YAPE",
        "numero_operacion": "99881122",
        "fecha_operacion": "2026-10-15",
        "monto": "150.00",
        "url_voucher": "https://s3.local/vouchers/voucher_yape.jpg",
    }
    # 1. Primer reporte
    res1 = client.post("/api/v1/pagos/reportar", json=payload)
    assert res1.status_code == 202
    data1 = res1.json()
    assert data1["estado"] == "EN_REVISION"
    assert "idempotency_hash" in data1

    # 2. Reporte duplicado en revisión -> retorna el mismo comprobante sin duplicar
    res2 = client.post("/api/v1/pagos/reportar", json=payload)
    assert res2.status_code == 202
    assert res2.json()["comprobante_id"] == data1["comprobante_id"]


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual")
def test_api_reservas_flujo_completo():
    # 1. Catálogo de áreas comunes
    res_areas = client.get("/api/v1/areas")
    assert res_areas.status_code == 200
    areas = res_areas.json()
    assert len(areas) >= 4
    area_parrilla = next(a for a in areas if "Parrilla 1" in a["nombre"])
    area_id = area_parrilla["id"]

    # 2. Intento de reserva por dpto moroso (402) -> 403 Forbidden
    payload_moroso = {
        "condominio_id": str(uuid.uuid4()),
        "area_id": area_id,
        "departamento_id": "402",
        "fecha_reserva": "2026-10-25",
        "hora_inicio": "19:00",
        "hora_fin": "22:00",
    }
    res_moroso = client.post("/api/v1/reservas", json=payload_moroso)
    assert res_moroso.status_code == 403
    assert res_moroso.json()["detail"]["error_code"] == "DEUDA_MORA_ACTIVA"

    # 3. Reserva exitosa por residente solvente (102) -> 201 Created
    payload_solvente = {
        "condominio_id": str(uuid.uuid4()),
        "area_id": area_id,
        "departamento_id": "102",
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
        "condominio_id": str(uuid.uuid4()),
        "area_id": area_id,
        "departamento_id": "104",
        "fecha_reserva": "2026-10-25",
        "hora_inicio": "20:00",
        "hora_fin": "23:00",
    }
    res_conflicto = client.post("/api/v1/reservas", json=payload_conflicto)
    assert res_conflicto.status_code == 409
    assert res_conflicto.json()["detail"]["error_code"] == "HORARIO_NO_DISPONIBLE"

    # 5. Cancelación por administración -> 200 OK
    res_cancelar = client.post(
        f"/api/v1/reservas/{reserva_id}/cancelar",
        json={"motivo": "Fumigación de la terraza", "es_admin": True},
    )
    assert res_cancelar.status_code == 200
    assert res_cancelar.json()["estado"] == "CANCELADA"
