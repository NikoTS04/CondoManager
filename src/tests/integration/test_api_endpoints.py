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
    """Flujo completo contra PostgreSQL: catálogo, solvencia, conflicto, consulta y cancelación."""
    from src.tests.integration.db_pruebas import borrar_condominio, crear_condominio_de_prueba

    sufijo = uuid.uuid4().hex[:8]
    condominio = crear_condominio_de_prueba(client, sufijo)

    try:
        # 1. Alta de áreas comunes (catálogo persistido en `areas_comunes`)
        res_area = client.post(
            "/api/v1/areas/crear",
            json={
                "condominio_id": condominio["id"],
                "nombre": f"Parrilla 1 Pruebas {sufijo}",
                "descripcion": "Terraza con parrilla",
                "aforo_maximo": 12,
                "costo_reserva": "25.00",
            },
        )
        assert res_area.status_code == 201, res_area.text
        area_id = res_area.json()["id"]

        # 2. Alta de departamentos: dos solventes y uno en mora
        departamentos = {}
        lotes = (
            (f"{sufijo[:4]}1", "AL_DIA", "solvente"),
            (f"{sufijo[:4]}2", "EN_MORA", "moroso"),
            (f"{sufijo[:4]}3", "AL_DIA", "competidor"),
        )
        for numero, estado, clave in lotes:
            res_dpto = client.post(
                "/api/v1/departamentos/crear",
                json={
                    "condominio_id": condominio["id"],
                    "numero": numero,
                    "piso": 1,
                    "coeficiente_participacion": "0.6800",
                    "estado_financiero": estado,
                },
            )
            assert res_dpto.status_code == 201, res_dpto.text
            departamentos[clave] = res_dpto.json()

        # 3. Catálogo de áreas: el área creada está disponible
        res_areas = client.get("/api/v1/areas")
        assert res_areas.status_code == 200
        areas = res_areas.json()
        assert any(a["id"] == area_id for a in areas)

        # 4. Departamento en mora -> 403 Forbidden
        res_moroso = client.post(
            "/api/v1/reservas",
            json={
                "condominio_id": condominio["id"],
                "area_id": area_id,
                "departamento_id": departamentos["moroso"]["id"],
                "fecha_reserva": "2026-12-24",
                "hora_inicio": "19:00",
                "hora_fin": "22:00",
            },
        )
        assert res_moroso.status_code == 403
        assert res_moroso.json()["detail"]["error_code"] == "DEUDA_MORA_ACTIVA"

        # 5. Departamento solvente -> 201 Created / CONFIRMADA
        res_solvente = client.post(
            "/api/v1/reservas",
            json={
                "condominio_id": condominio["id"],
                "area_id": area_id,
                "departamento_id": departamentos["solvente"]["id"],
                "fecha_reserva": "2026-12-24",
                "hora_inicio": "19:00",
                "hora_fin": "22:00",
            },
        )
        assert res_solvente.status_code == 201, res_solvente.text
        reserva_creada = res_solvente.json()
        assert reserva_creada["estado"] == "CONFIRMADA"
        assert reserva_creada["condominio_id"] == condominio["id"]
        reserva_id = reserva_creada["id"]

        # 6. Conflicto de horario -> 409 Conflict
        res_conflicto = client.post(
            "/api/v1/reservas",
            json={
                "condominio_id": condominio["id"],
                "area_id": area_id,
                "departamento_id": departamentos["competidor"]["id"],
                "fecha_reserva": "2026-12-24",
                "hora_inicio": "20:00",
                "hora_fin": "23:00",
            },
        )
        assert res_conflicto.status_code == 409
        assert res_conflicto.json()["detail"]["error_code"] == "HORARIO_NO_DISPONIBLE"

        # 7. Consulta de disponibilidad: la reserva confirmada ocupa la franja
        res_consulta = client.get(
            f"/api/v1/reservas?area_id={area_id}&fecha=2026-12-24"
        )
        assert res_consulta.status_code == 200
        assert [r["id"] for r in res_consulta.json()] == [reserva_id]

        # 8. Cancelación por administración -> 200 OK y la franja se libera
        res_cancelar = client.post(
            f"/api/v1/reservas/{reserva_id}/cancelar",
            json={"motivo": "Fumigación de la terraza", "es_admin": True},
        )
        assert res_cancelar.status_code == 200
        assert res_cancelar.json()["estado"] == "CANCELADA"

        res_tras_cancelar = client.get(
            f"/api/v1/reservas?area_id={area_id}&fecha=2026-12-24"
        )
        assert res_tras_cancelar.json() == []
    finally:
        borrar_condominio(condominio["id"])


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual")
def test_api_notificaciones_endpoints():
    # 1. Despacho individual
    payload_despacho = {
        "condominio_id": "vb3-condo",
        "departamento_id": "105",
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
    assert res_despacho.status_code == 201
    log_id = res_despacho.json()["id"]

    # 2. Consulta de logs
    res_logs = client.get("/api/v1/notificaciones/logs?departamento_id=105")
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
    assert res_reenviar.json()["destinatario"] == "nuevo_residente105@gmail.com"

    # 4. Comunicado masivo
    payload_masivo = {
        "condominio_id": "vb3-condo",
        "titulo": "Asamblea General de Propietarios",
        "mensaje": "Se convoca a la asamblea anual ordinaria para el próximo mes.",
        "canal": "EMAIL",
        "remitente": "Junta Directiva",
    }
    res_masivo = client.post("/api/v1/notificaciones/comunicado-masivo", json=payload_masivo)
    assert res_masivo.status_code == 202
    data_masivo = res_masivo.json()
    assert data_masivo["total_destinatarios"] == 139
    assert data_masivo["notificaciones_generadas"] == 139
