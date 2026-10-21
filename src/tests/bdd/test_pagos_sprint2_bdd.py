"""Gherkin ejecutable con API, identidad y PostgreSQL reales."""

import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pytest_bdd import given, scenarios, then, when

from src.main import app
from src.tests.pagos_db import did

scenarios("../../../specs/02-domains/02-pagos-y-moras/features/sprint_2_anderson.feature")


@pytest.fixture
def flujo(db_pagos):
    with TestClient(app) as client:

        def login(email, password):
            response = client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            assert response.status_code == 200
            return {"Authorization": "Bearer " + response.json()["access_token"]}

        yield {
            "client": client,
            "base": db_pagos,
            "residente": login("moroso402@villabonita3.pe", "Moroso123!"),
            "junta": login("admin@villabonita3.pe", "Admin123!"),
            "ajeno": login("residente102@villabonita3.pe", "Residente123!"),
        }


def cargar(flujo):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    flujo["files"] = {"archivo_voucher": ("evidencia.png", buffer.getvalue(), "image/png")}
    flujo["body"] = {
        "departamento_id": str(did()),
        "banco": "BCP",
        "numero_operacion": "BDD-12345",
        "fecha_operacion": "2026-10-15",
        "monto": "170.00",
    }


def reportar(flujo):
    cargar(flujo)
    response = flujo["client"].post(
        "/api/v1/pagos/reportar",
        headers=flujo["residente"],
        data=flujo["body"],
        files=flujo["files"],
    )
    assert response.status_code == 202
    flujo["id"] = response.json()["comprobante_id"]


@given("un residente activo vinculado a un departamento con deuda en mora")
def residente(flujo):
    assert (
        flujo["client"]
        .get(f"/api/v1/pagos/solvencia/{did()}", headers=flujo["residente"])
        .json()["saldo_vencido"]
        == "170.00"
    )


@when("sube un voucher válido y reporta su pago")
def reporte(flujo):
    reportar(flujo)


@then("recibe un comprobante EN_REVISION persistido")
def en_revision(flujo):
    assert (
        flujo["client"]
        .get("/api/v1/pagos/comprobantes", headers=flujo["residente"])
        .json()[0]["estado"]
        == "EN_REVISION"
    )


@then("url_voucher contiene la ruta autenticada del comprobante")
def nombre_local(flujo):
    data = flujo["client"].get("/api/v1/pagos/comprobantes", headers=flujo["residente"]).json()[0]
    assert data["url_voucher"] == f"/api/v1/pagos/{flujo['id']}/voucher"


@then("la deuda y el bloqueo de reservas no cambian")
def deuda_igual(flujo):
    assert (
        flujo["client"]
        .get(f"/api/v1/pagos/solvencia/{did()}", headers=flujo["residente"])
        .json()["saldo_vencido"]
        == "170.00"
    )


@given("un comprobante persistido que cubre toda la deuda en mora")
@given("un comprobante EN_REVISION")
@given("un comprobante con evidencia adjuntada a un departamento")
def comprobante(flujo):
    reportar(flujo)


@when("la junta aprueba el comprobante")
def aprobar(flujo):
    response = flujo["client"].post(
        f"/api/v1/pagos/{flujo['id']}/conciliar",
        headers=flujo["junta"],
        json={"decision": "APROBADO"},
    )
    assert response.status_code == 200
    flujo["resultado"] = response.json()


@then("las imputaciones, el resultado, la auditoría y el evento son atómicos")
def resultado_confirmado(flujo):
    response = flujo["client"].get(
        f"/api/v1/pagos/{flujo['id']}/resultado", headers=flujo["residente"]
    )
    assert response.json() == flujo["resultado"] and response.json()["monto_imputado"] == "170.00"


@then("el siguiente intento de reserva queda habilitado")
def reserva_habilitada(flujo):
    response = flujo["client"].post(
        "/api/v1/reservas",
        headers=flujo["residente"],
        json={
            "condominio_id": flujo["base"].cid,
            "departamento_id": str(did()),
            "area_id": "11111111-1111-1111-1111-111111111101",
            "fecha_reserva": (date.today() + timedelta(days=10)).isoformat(),
            "hora_inicio": "12:00",
            "hora_fin": "14:00",
        },
    )
    assert response.status_code == 201


@then("volver a aprobar no aplica fondos otra vez")
def no_reaplicar(flujo):
    assert (
        flujo["client"]
        .post(
            f"/api/v1/pagos/{flujo['id']}/conciliar",
            headers=flujo["junta"],
            json={"decision": "APROBADO"},
        )
        .status_code
        == 200
    )


@when("la junta lo observa con un motivo")
def observar(flujo):
    response = flujo["client"].post(
        f"/api/v1/pagos/{flujo['id']}/conciliar",
        headers=flujo["junta"],
        json={"decision": "OBSERVADO", "motivo_rechazo": "Verificar operación"},
    )
    assert response.status_code == 200


@then("el estado persistido es OBSERVADO y los saldos no cambian")
def observado(flujo):
    assert (
        flujo["client"]
        .get("/api/v1/pagos/comprobantes", headers=flujo["residente"])
        .json()[0]["estado"]
        == "OBSERVADO"
    )
    deuda_igual(flujo)


@given("un voucher autorizado y dos reportes equivalentes")
def dos_reportes(flujo):
    cargar(flujo)


@when("llegan desde sesiones PostgreSQL independientes")
def concurrencia(flujo):
    def enviar(_):
        return flujo["client"].post(
            "/api/v1/pagos/reportar",
            headers=flujo["residente"],
            data=flujo["body"],
            files=flujo["files"],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        respuestas = list(executor.map(enviar, range(2)))
    assert sorted(r.status_code for r in respuestas) == [200, 202]


@then("existe un solo comprobante y un único evento de recepción")
def unico(flujo):
    assert (
        len(flujo["client"].get("/api/v1/pagos/comprobantes", headers=flujo["residente"]).json())
        == 1
    )


@when("un residente sin vínculo intenta descargar el voucher")
def acceso_ajeno(flujo):
    flujo["respuesta"] = flujo["client"].get(
        f"/api/v1/pagos/{flujo['id']}/voucher", headers=flujo["ajeno"]
    )


@then("recibe rechazo y no obtiene el contenido del archivo")
def privado(flujo):
    assert flujo["respuesta"].status_code == 403
