"""Pruebas de contrato HTTP para CON-2 sin depender de infraestructura externa."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.security import create_access_token
from src.main import app
from src.modules.condominios.router import get_condominio_repository
from src.tests.fakes import FakeCondominioRepository


@pytest.fixture
def repository():
    fake = FakeCondominioRepository()
    app.dependency_overrides[get_condominio_repository] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_condominio_repository, None)


@pytest.fixture
def client(repository):
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(rol: str = "SUPERADMIN", subject: str | None = None) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": subject or str(uuid4()),
            "email": "superadmin@condomanager.pe",
            "rol": rol,
            "condominio_id": None,
            "departamentos": [],
        }
    )
    return {"Authorization": f"Bearer {token}"}


def payload(nombre: str = "Villa Bonita 3") -> dict[str, object]:
    return {
        "nombre": nombre,
        "direccion": "Av. Principal 123, Lima",
        "moneda": "PEN",
        "regla_mora_tipo": "MONTO_FIJO",
        "monto_mora_fijo": "20.00",
        "tasa_mora_porcentaje": None,
        "dia_vencimiento": 20,
        "dias_gracia": 2,
    }


def test_superadmin_crea_y_consulta_condominio(client, repository):
    actor_id = str(uuid4())
    response = client.post(
        "/api/v1/condominios",
        json=payload(),
        headers=auth_headers(subject=actor_id),
    )

    assert response.status_code == 201
    creado = response.json()
    assert creado["activo"] is True
    assert creado["monto_mora_fijo"] == "20.00"
    assert creado["tasa_mora_porcentaje"] is None
    assert creado["creado_en"].endswith(("Z", "+00:00"))

    consulta = client.get(f"/api/v1/condominios/{creado['id']}", headers=auth_headers())
    assert consulta.status_code == 200
    assert consulta.json() == creado

    assert len(repository.auditorias) == 1
    auditoria = repository.auditorias[0]
    assert auditoria.accion_ejecutada == "CONDOMINIO_CREADO"
    assert auditoria.actor_id == actor_id
    assert str(auditoria.condominio_id) == creado["id"]


def test_creacion_exige_autenticacion_y_rol_superadmin(client, repository):
    sin_token = client.post("/api/v1/condominios", json=payload())
    assert sin_token.status_code == 401
    assert sin_token.json()["error_code"] == "NO_AUTENTICADO"

    rol_incorrecto = client.post(
        "/api/v1/condominios",
        json=payload(),
        headers=auth_headers("ADMIN_JUNTA"),
    )
    assert rol_incorrecto.status_code == 403
    assert rol_incorrecto.json()["error_code"] == "ACCESO_DENEGADO"
    assert repository.condominios == {}


def test_configuracion_de_mora_invalida_no_se_persiste(client, repository):
    invalido = payload()
    invalido.update(
        {
            "regla_mora_tipo": "PORCENTAJE_SALDO",
            "monto_mora_fijo": "20.00",
            "tasa_mora_porcentaje": None,
        }
    )
    response = client.post("/api/v1/condominios", json=invalido, headers=auth_headers())
    assert response.status_code == 422
    assert response.json()["error_code"] == "DATOS_CONDOMINIO_INVALIDOS"
    assert repository.condominios == {}
    assert repository.auditorias == []


def test_consulta_inexistente_devuelve_404(client):
    condominio_id = uuid4()
    response = client.get(f"/api/v1/condominios/{condominio_id}", headers=auth_headers())
    assert response.status_code == 404
    assert response.json() == {
        "error_code": "CONDOMINIO_NO_ENCONTRADO",
        "mensaje": "No existe un condominio con el identificador solicitado.",
        "detalles": {"condominio_id": str(condominio_id)},
    }


def test_dos_condominios_permanecen_aislados(client):
    norte = payload("Condominio Norte")
    sur = payload("Condominio Sur")
    sur.update({"moneda": "USD", "dia_vencimiento": 15})

    creado_norte = client.post("/api/v1/condominios", json=norte, headers=auth_headers()).json()
    creado_sur = client.post("/api/v1/condominios", json=sur, headers=auth_headers()).json()

    assert creado_norte["id"] != creado_sur["id"]
    consulta_norte = client.get(
        f"/api/v1/condominios/{creado_norte['id']}", headers=auth_headers()
    ).json()
    consulta_sur = client.get(
        f"/api/v1/condominios/{creado_sur['id']}", headers=auth_headers()
    ).json()

    assert consulta_norte["nombre"] == "Condominio Norte"
    assert consulta_norte["moneda"] == "PEN"
    assert consulta_sur["nombre"] == "Condominio Sur"
    assert consulta_sur["moneda"] == "USD"
