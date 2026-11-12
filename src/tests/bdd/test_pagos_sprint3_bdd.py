"""CON-25–28 ejecutables con login, autorización y productor PostgreSQL reales."""

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.main import app
from src.tests.integration.test_pagos_db import imagen
from src.tests.pagos_db import did
from src.tests.pagos_sprint3 import fijar_reloj, preparar

scenarios("../../../specs/02-domains/02-pagos-y-moras/features/sprint_3_anderson.feature")


@pytest.fixture
def flujo(db_usuarios, monkeypatch, tmp_path):
    fijar_reloj(monkeypatch, tmp_path)
    asyncio.run(preparar(db_usuarios))
    with TestClient(app) as client:

        def login(cuenta, password):
            r = client.post(
                "/api/v1/auth/login",
                json={
                    "email": cuenta + "@villabonita3.pe",
                    "password": password,
                },
            )
            assert r.status_code == 200, r.text
            return {"Authorization": "Bearer " + r.json()["access_token"]}

        yield {
            "client": client,
            "residente": login("residente102", "Residente123!"),
            "junta": login("admin", "Admin123!"),
        }


def cuenta(flujo):
    r = flujo["client"].get(
        f"/api/v1/cuotas/departamentos/{did('102')}/estado-cuenta"
        "?desde=2026-01-01&hasta=2026-12-31",
        headers=flujo["residente"],
    )
    assert r.status_code == 200, r.text
    return r.json()


def reportar(flujo, monto):
    r = flujo["client"].post(
        "/api/v1/pagos/reportar",
        headers=flujo["residente"],
        data={
            "departamento_id": str(did("102")),
            "banco": "BCP",
            "numero_operacion": uuid4().hex,
            "fecha_operacion": "2026-10-10",
            "monto": monto,
        },
        files={"archivo_voucher": ("bdd.png", imagen(), "image/png")},
    )
    assert r.status_code == 202, r.text
    flujo["id"] = r.json()["comprobante_id"]


@given(parsers.parse('una unidad autorizada con deuda fija de "{monto}"'))
def deuda(flujo, monto):
    assert cuenta(flujo)["deuda_actual"] == monto


@when(parsers.parse('la junta aprueba un comprobante de "{monto}"'))
def aprobar(flujo, monto):
    reportar(flujo, monto)
    flujo["monto"] = monto
    r = flujo["client"].post(
        f"/api/v1/pagos/{flujo['id']}/conciliar",
        headers=flujo["junta"],
        json={"decision": "APROBADO"},
    )
    assert r.status_code == 200, r.text
    flujo["resultado"] = r.json()


@then(parsers.parse('la deuda restante es "{deuda}" y el crédito es "{credito}"'))
def saldos(flujo, deuda, credito):
    c = cuenta(flujo)
    assert c["deuda_actual"] == deuda and c["saldo_a_favor_actual"] == credito
    assert flujo["resultado"]["nuevo_saldo_departamento"] == deuda


@then("repetir la aprobación recupera el mismo recibo")
def repetir(flujo):
    r = flujo["client"].post(
        f"/api/v1/pagos/{flujo['id']}/conciliar",
        headers=flujo["junta"],
        json={"decision": "APROBADO"},
    )
    assert r.status_code == 200 and r.json() == flujo["resultado"]


@then("la unidad conserva el bloqueo de reservas por deuda vencida")
def bloqueo(flujo):
    r = flujo["client"].get(f"/api/v1/pagos/solvencia/{did('102')}", headers=flujo["residente"])
    assert r.status_code == 200 and r.json()["habilitado_reservas"] is False


@then("el estado de cuenta identifica el pago sin duplicar su abono")
def origen(flujo):
    c = cuenta(flujo)
    assert c["abonos_periodo"] == flujo["monto"]
    assert [m["comprobante_id"] for m in c["movimientos"] if m["tipo"] == "PAGO_APROBADO"] == [
        flujo["id"]
    ]


@when("la junta observa un comprobante y el residente subsana la evidencia")
def subsanar(flujo):
    reportar(flujo, "100.00")
    r = flujo["client"].post(
        f"/api/v1/pagos/{flujo['id']}/conciliar",
        headers=flujo["junta"],
        json={"decision": "OBSERVADO", "motivo_rechazo": "Imagen ilegible"},
    )
    assert r.status_code == 200, r.text
    flujo["evidencia"] = (
        flujo["client"]
        .get(
            f"/api/v1/pagos/{flujo['id']}/evidencias",
            headers=flujo["residente"],
        )
        .json()[0]["evidencia_id"]
    )
    r = flujo["client"].put(
        f"/api/v1/pagos/{flujo['id']}/voucher",
        headers=flujo["residente"],
        files={"archivo_voucher": ("nueva.png", imagen(), "image/png")},
    )
    assert r.status_code == 202, r.text


@then("la deuda sigue intacta y el comprobante vuelve a EN_REVISION")
def pendiente(flujo):
    c = cuenta(flujo)
    assert c["deuda_actual"] == "100.00" and c["pagos_en_revision"][0]["id"] == flujo["id"]


@then("se conserva la evidencia de la revisión anterior")
def evidencia(flujo):
    r = flujo["client"].get(
        f"/api/v1/pagos/{flujo['id']}/voucher?evidencia_id={flujo['evidencia']}",
        headers=flujo["residente"],
    )
    assert r.status_code == 200 and r.content == imagen()
