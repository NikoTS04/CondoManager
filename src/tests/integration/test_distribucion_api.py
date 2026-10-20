"""Contrato HTTP de CON-10 con repositorio sustituible, igual que CON-9."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.security import create_access_token
from src.main import app
from src.modules.cuotas.distribucion.router import get_distribucion_repository
from src.tests.unit.test_distribucion_service import FakeDistribucionRepository, departamentos

pytestmark = pytest.mark.usefixtures("autorizacion_aislada")


@pytest.fixture
def repository():
    repo = FakeDistribucionRepository()
    app.dependency_overrides[get_distribucion_repository] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_distribucion_repository, None)


@pytest.fixture
def client(repository):
    with TestClient(app) as cliente:
        yield cliente


def headers(rol, condominio_id, actor="administrador"):
    token = create_access_token(
        {
            "sub": actor,
            "rol": rol,
            "condominio_id": str(condominio_id) if condominio_id is not None else None,
            "departamentos": [],
        }
    )
    return {"Authorization": f"Bearer {token}"}


def ruta(repo):
    return f"/api/v1/condominios/{repo.condominio_id}/distribucion"


@pytest.mark.parametrize("metodo", ["POR_ALICUOTA", "EQUITATIVA"])
def test_configura_consulta_y_repite_put(client, repository, metodo):
    auth = headers("ADMIN_JUNTA", repository.condominio_id)
    creado = client.put(ruta(repository), json={"metodo": metodo}, headers=auth)
    assert creado.status_code == 200
    datos = creado.json()
    assert datos["condominio_id"] == str(repository.condominio_id)
    assert datos["metodo"] == metodo
    assert datos["actualizado_por"] == "administrador"
    assert datos["actualizado_en"].endswith("Z")
    consulta = client.get(ruta(repository), headers=headers("AUDITOR", repository.condominio_id))
    repetido = client.put(ruta(repository), json={"metodo": metodo}, headers=auth)
    assert consulta.status_code == repetido.status_code == 200
    assert consulta.json() == repetido.json() == datos
    assert len(repository.configuraciones) == len(repository.auditorias) == 1


@pytest.mark.parametrize("suma", ["99.9999", "100.0001"])
def test_rechaza_coeficientes_inexactos_sin_persistir(client, repository, suma):
    repository.departamentos[repository.condominio_id] = departamentos(
        "50", str(Decimal(suma) - Decimal(50))
    )
    response = client.put(
        ruta(repository),
        json={"metodo": "POR_ALICUOTA"},
        headers=headers("ADMIN_JUNTA", repository.condominio_id),
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "DISTRIBUCION_COEFICIENTES_INVALIDOS"
    assert response.json()["detalles"]["suma_coeficientes"] == suma
    assert response.json()["mensaje"]
    assert repository.configuraciones == {}
    assert repository.auditorias == []


@pytest.mark.parametrize("metodo", ["POR_ALICUOTA", "EQUITATIVA"])
def test_rechaza_sin_departamentos(client, repository, metodo):
    repository.departamentos.clear()
    response = client.put(
        ruta(repository),
        json={"metodo": metodo},
        headers=headers("ADMIN_JUNTA", repository.condominio_id),
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "DISTRIBUCION_SIN_DEPARTAMENTOS"
    assert repository.auditorias == []


@pytest.mark.parametrize("operacion", ["get", "put"])
def test_exige_token_y_aislamiento(client, repository, operacion):
    argumentos = {"json": {"metodo": "EQUITATIVA"}} if operacion == "put" else {}
    solicitar = getattr(client, operacion)
    assert solicitar(ruta(repository), **argumentos).status_code == 401
    for rol, contexto in [
        ("ADMIN_JUNTA", uuid4()),
        ("AUDITOR", uuid4()),
        ("RESIDENTE", repository.condominio_id),
        ("ADMIN_JUNTA", None),
    ]:
        respuesta = solicitar(ruta(repository), headers=headers(rol, contexto), **argumentos)
        assert respuesta.status_code == 403
        assert respuesta.json()["error_code"] == "DISTRIBUCION_ACCESO_DENEGADO"
    assert repository.configuraciones == {}
    assert repository.auditorias == []


def test_auditor_no_escribe_y_superadmin_puede_operar_sin_contexto(client, repository):
    respuesta = client.put(
        ruta(repository),
        json={"metodo": "EQUITATIVA"},
        headers=headers("AUDITOR", repository.condominio_id),
    )
    assert respuesta.status_code == 403
    respuesta = client.put(
        ruta(repository),
        json={"metodo": "EQUITATIVA"},
        headers=headers("SUPERADMIN", None),
    )
    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "payload", [{}, {"metodo": "FIJA"}, {"metodo": 1.5}, {"metodo": "EQUITATIVA", "extra": "no"}]
)
def test_contrato_invalido(client, repository, payload):
    response = client.put(
        ruta(repository),
        json=payload,
        headers=headers("ADMIN_JUNTA", repository.condominio_id),
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "DATOS_DISTRIBUCION_INVALIDOS"
    assert repository.auditorias == []


def test_configuracion_ausente_y_condominio_inexistente(client, repository):
    response = client.get(
        ruta(repository), headers=headers("ADMIN_JUNTA", repository.condominio_id)
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "DISTRIBUCION_NO_CONFIGURADA"
    repository.condominios.clear()
    response = client.put(
        ruta(repository),
        json={"metodo": "EQUITATIVA"},
        headers=headers("SUPERADMIN", None),
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "CONDOMINIO_NO_ENCONTRADO"


def test_no_mezcla_datos_de_dos_condominios(client, repository):
    auth = headers("SUPERADMIN", None)
    primero = client.put(ruta(repository), json={"metodo": "POR_ALICUOTA"}, headers=auth)
    otro = uuid4()
    repository.condominios[otro] = object()
    repository.departamentos[otro] = departamentos("1")
    otra_ruta = f"/api/v1/condominios/{otro}/distribucion"
    segundo = client.put(otra_ruta, json={"metodo": "EQUITATIVA"}, headers=auth)
    assert primero.status_code == segundo.status_code == 200
    assert primero.json()["id"] != segundo.json()["id"]
    assert client.get(ruta(repository), headers=auth).json()["metodo"] == "POR_ALICUOTA"
    assert client.get(otra_ruta, headers=auth).json()["metodo"] == "EQUITATIVA"
