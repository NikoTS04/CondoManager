"""Pruebas unitarias/API de CON-51 con persistencia aislada y storage falso."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.core.security import get_current_user
from src.main import app
from src.modules.cuotas.presupuestos.models import ConceptoPresupuestal


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def scalar(self, _statement):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    def in_transaction(self):
        return True


class FakeEgresosRepository:
    def __init__(self, _session, state):
        self.state = state

    async def bloquear_condominio(self, condominio_id):
        return self.state.condominios.get(condominio_id)

    async def obtener_condominio(self, condominio_id):
        return self.state.condominios.get(condominio_id)

    async def obtener_concepto(self, condominio_id, concepto_id):
        concepto = self.state.conceptos.get(concepto_id)
        if concepto and concepto.condominio_id == condominio_id and concepto.activo:
            return concepto
        return None

    async def obtener_presupuesto(self, condominio_id, presupuesto_id):
        presupuesto = self.state.presupuestos.get(presupuesto_id)
        return presupuesto if presupuesto and presupuesto.condominio_id == condominio_id else None

    async def agregar_egreso(self, egreso):
        egreso.concepto = self.state.conceptos[egreso.concepto_id]
        self.state.egresos[egreso.id] = egreso
        return egreso

    async def obtener_egreso(self, condominio_id, egreso_id, *, bloquear=False):
        egreso = self.state.egresos.get(egreso_id)
        if egreso is None or egreso.condominio_id != condominio_id:
            return None
        egreso.concepto = self.state.conceptos[egreso.concepto_id]
        return egreso

    async def listar_egresos(self, condominio_id, **filters):
        rows = [e for e in self.state.egresos.values() if e.condominio_id == condominio_id]
        if filters.get("fecha_desde"):
            rows = [e for e in rows if e.fecha_gasto >= filters["fecha_desde"]]
        if filters.get("fecha_hasta"):
            rows = [e for e in rows if e.fecha_gasto <= filters["fecha_hasta"]]
        if filters.get("estado"):
            rows = [e for e in rows if e.estado == filters["estado"]]
        if filters.get("proveedor_id"):
            rows = [e for e in rows if e.proveedor_id == filters["proveedor_id"]]
        if filters.get("concepto_id"):
            rows = [e for e in rows if e.concepto_id == filters["concepto_id"]]
        rows.sort(key=lambda e: (e.fecha_gasto, str(e.id)), reverse=True)
        offset, limit = filters["offset"], filters["limit"]
        return rows[offset : offset + limit], len(rows) > offset + limit

    async def agregar_documento(self, documento):
        egreso = self.state.egresos[documento.egreso_id]
        egreso.documentos.append(documento)
        self.state.documentos[documento.id] = documento
        return documento

    async def obtener_documento(self, condominio_id, documento_id, *, egreso_id=None):
        documento = self.state.documentos.get(documento_id)
        if (
            documento is None
            or documento.condominio_id != condominio_id
            or (egreso_id is not None and documento.egreso_id != egreso_id)
        ):
            return None
        return documento


class FakeState:
    def __init__(self):
        self.condominios = {}
        self.conceptos = {}
        self.presupuestos = {}
        self.egresos = {}
        self.documentos = {}
        self.repo = None
        self.session = FakeSession()
        self.storage = None


class FakePrivateStorage:
    def __init__(self):
        self.files = {}
        self.removed = []

    def validar(self, contenido):
        if not contenido.startswith(b"%PDF-"):
            raise APIError(415, "FORMATO_NO_SOPORTADO", "Use PDF, JPEG o PNG.")
        return "pdf", "application/pdf"

    def guardar(self, contenido):
        key = f"{uuid4()}.pdf"
        self.files[key] = contenido
        return key, "application/pdf"

    def leer(self, key):
        if key not in self.files:
            raise APIError(404, "DOCUMENTO_NO_DISPONIBLE", "No existe el documento.")
        return self.files[key]

    def eliminar(self, key):
        self.removed.append(key)
        self.files.pop(key, None)


@pytest.fixture
def api_egresos(monkeypatch):
    state = FakeState()
    cid = uuid4()
    concepto_id = uuid4()
    state.condominios[cid] = SimpleNamespace(id=cid, activo=True)
    state.conceptos[concepto_id] = ConceptoPresupuestal(
        id=concepto_id,
        condominio_id=cid,
        codigo="SER-01",
        categoria="SERVICIOS_BASICOS",
        descripcion="Servicios comunes",
        activo=True,
    )
    state.storage = FakePrivateStorage()
    monkeypatch.setattr(
        "src.modules.egresos.service.SQLAlchemyEgresosRepository",
        lambda session: FakeEgresosRepository(session, state),
    )
    monkeypatch.setattr("src.modules.egresos.service.get_egresos_storage", lambda: state.storage)

    async def sesion():
        yield state.session

    actor_holder = {"actor": {"sub": str(uuid4()), "rol": "ADMIN_JUNTA", "condominio_id": str(cid)}}

    async def current_user():
        return actor_holder["actor"]

    monkeypatch.setitem(app.dependency_overrides, get_db_session, sesion)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, current_user)
    with TestClient(app) as client:
        yield client, state, cid, concepto_id, actor_holder
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


def body(concepto_id):
    return {
        "concepto_id": str(concepto_id),
        "descripcion": "Servicio de limpieza",
        "justificacion": "Factura mensual de noviembre",
        "moneda": "PEN",
        "fecha_gasto": "2026-11-20",
        "monto_solicitado": "250.00",
    }


def test_api_registra_borrador_sin_proveedor_pago_ni_caja(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    response = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["estado"] == "BORRADOR"
    assert data["proveedor_id"] is None and data["contrato_id"] is None
    assert data["monto_solicitado"] == "250.00"
    assert data["monto_pagado"] == "0.00"
    assert data["categoria"] == "SERVICIOS_BASICOS"
    assert data["pagos"] == []
    assert data["documentos"] == []
    assert any(isinstance(row, AuditoriaLogORM) for row in state.session.added)
    audit = next(row for row in state.session.added if isinstance(row, AuditoriaLogORM))
    assert audit.accion_ejecutada == "EGRESO_CREADO"
    assert audit.hash_actual and len(audit.hash_actual) == 64


@pytest.mark.parametrize("field", ["proveedor_id", "contrato_id"])
def test_api_rechaza_referencias_no_integradas_sin_crear_egreso(api_egresos, field):
    client, state, cid, concepto_id, _ = api_egresos
    payload = body(concepto_id)
    payload[field] = str(uuid4())
    if field == "contrato_id":
        payload["proveedor_id"] = str(uuid4())
    response = client.post(f"/api/v1/condominios/{cid}/egresos", json=payload)
    assert response.status_code == 409
    assert response.json()["error_code"] == "PROVEEDOR_NO_DISPONIBLE"
    assert state.egresos == {}


def test_api_rechaza_concepto_inactivo_o_ajeno(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    state.conceptos[concepto_id].activo = False
    response = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    assert response.status_code == 422
    assert response.json()["error_code"] == "CONCEPTO_PRESUPUESTAL_NO_DISPONIBLE"
    assert state.egresos == {}


def test_api_rechaza_concepto_de_otro_condominio(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    otro_condominio = uuid4()
    state.conceptos[concepto_id].condominio_id = otro_condominio
    response = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    assert response.status_code == 422
    assert response.json()["error_code"] == "CONCEPTO_PRESUPUESTAL_NO_DISPONIBLE"
    assert state.egresos == {}


def test_api_lista_filtra_y_oculta_otro_condominio(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    assert (
        client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id)).status_code == 201
    )
    otro = uuid4()
    state.condominios[otro] = SimpleNamespace(id=otro, activo=True)
    response = client.get(f"/api/v1/condominios/{cid}/egresos?estado=BORRADOR&limit=10")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert client.get(f"/api/v1/condominios/{otro}/egresos").status_code == 403


def test_api_detalle_edicion_versionada_y_conflicto_de_version(api_egresos):
    client, _state, cid, concepto_id, _ = api_egresos
    created = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    egreso_id = created.json()["id"]
    detalle = client.get(f"/api/v1/condominios/{cid}/egresos/{egreso_id}")
    assert detalle.status_code == 200
    assert detalle.json()["version"] == 1
    updated = client.patch(
        f"/api/v1/condominios/{cid}/egresos/{egreso_id}",
        json={"version_esperada": 1, "monto_solicitado": "275.00"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["monto_solicitado"] == "275.00"
    conflict = client.patch(
        f"/api/v1/condominios/{cid}/egresos/{egreso_id}",
        json={"version_esperada": 1, "monto_solicitado": "300.00"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "EGRESO_VERSION_OBSOLETA"


def test_auditor_puede_consultar_pero_no_escribir(api_egresos):
    client, _state, cid, concepto_id, actor_holder = api_egresos
    actor_holder["actor"] = {
        "sub": str(uuid4()),
        "rol": "AUDITOR",
        "condominio_id": str(cid),
    }
    assert client.get(f"/api/v1/condominios/{cid}/egresos").status_code == 200
    write = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    assert write.status_code == 403


def test_documentos_son_privados_y_no_exponen_storage_key(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    created = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    egreso_id = created.json()["id"]
    uploaded = client.post(
        f"/api/v1/condominios/{cid}/egresos/{egreso_id}/documentos",
        data={"tipo": "SUSTENTO"},
        files={"archivo": ("../../factura.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["tipo"] == "SUSTENTO"
    assert document["archivo_nombre"] == "factura.pdf"
    assert "storage_key" not in document and "url" not in document
    key = state.documentos[UUID(document["id"])].storage_key
    assert (
        client.get(
            f"/api/v1/condominios/{cid}/egresos/{egreso_id}/documentos/{document['id']}"
        ).content
        == b"%PDF-1.7\n%%EOF"
    )

    other_condo = uuid4()
    state.condominios[other_condo] = SimpleNamespace(id=other_condo, activo=True)
    private = client.get(
        f"/api/v1/condominios/{other_condo}/egresos/{egreso_id}/documentos/{document['id']}"
    )
    assert private.status_code == 403
    assert key not in uploaded.text
    audit = [row for row in state.session.added if isinstance(row, AuditoriaLogORM)]
    assert any(row.accion_ejecutada == "DOCUMENTO_EGRESO_ADJUNTADO" for row in audit)


def test_documento_invalido_y_excedido_no_se_persisten(api_egresos, monkeypatch):
    client, state, cid, concepto_id, _ = api_egresos
    created = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    egreso_id = created.json()["id"]
    invalid = client.post(
        f"/api/v1/condominios/{cid}/egresos/{egreso_id}/documentos",
        data={"tipo": "SUSTENTO"},
        files={"archivo": ("factura.pdf", b"no es pdf", "application/pdf")},
    )
    assert invalid.status_code == 415
    assert state.documentos == {}
    monkeypatch.setattr("src.modules.egresos.service.settings.VOUCHER_MAX_BYTES", 4)
    oversized = client.post(
        f"/api/v1/condominios/{cid}/egresos/{egreso_id}/documentos",
        data={"tipo": "SUSTENTO"},
        files={"archivo": ("factura.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert oversized.status_code == 413
    assert state.documentos == {}


def test_documento_pago_queda_para_con52(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    created = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    egreso_id = created.json()["id"]
    response = client.post(
        f"/api/v1/condominios/{cid}/egresos/{egreso_id}/documentos",
        data={"tipo": "EVIDENCIA_PAGO"},
        files={"archivo": ("transferencia.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CON52_NO_DISPONIBLE"
    assert len(state.storage.files) == 0


def test_invalidacion_entrada_monetaria_y_estado_no_editable(api_egresos):
    client, state, cid, concepto_id, _ = api_egresos
    payload = body(concepto_id)
    payload["monto_solicitado"] = "1.234"
    invalid = client.post(f"/api/v1/condominios/{cid}/egresos", json=payload)
    assert invalid.status_code == 422
    assert invalid.json()["error_code"] == "DATOS_EGRESO_INVALIDOS"
    created = client.post(f"/api/v1/condominios/{cid}/egresos", json=body(concepto_id))
    egreso = state.egresos[UUID(created.json()["id"])]
    egreso.estado = "APROBADO"
    response = client.patch(
        f"/api/v1/condominios/{cid}/egresos/{egreso.id}",
        json={"version_esperada": 1, "monto_solicitado": "300.00"},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "EGRESO_NO_EDITABLE"


def test_swagger_registra_rutas_con51_y_no_implementa_aprobacion():
    paths = app.openapi()["paths"]
    assert "/api/v1/condominios/{condominio_id}/egresos" in paths
    assert "/api/v1/condominios/{condominio_id}/egresos/{egreso_id}" in paths
    assert "/api/v1/condominios/{condominio_id}/egresos/{egreso_id}/documentos" in paths
    assert "/api/v1/condominios/{condominio_id}/egresos/{egreso_id}/aprobaciones" not in paths
