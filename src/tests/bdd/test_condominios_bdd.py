"""Ejecución de la especificación Gherkin de CON-2."""

from pathlib import Path
from uuid import uuid4

import pytest

try:
    from fastapi.testclient import TestClient
    from pytest_bdd import given, parsers, scenarios, then, when

    HAS_BDD_RUNTIME = True
except ImportError:
    HAS_BDD_RUNTIME = False

from src.core.security import create_access_token
from src.main import app
from src.modules.condominios.router import get_condominio_repository
from src.tests.fakes import FakeCondominioRepository

FEATURE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "02-domains"
    / "05-usuarios-rbac"
    / "features"
    / "condominios.feature"
)


def _payload(nombre: str = "Villa Bonita 3") -> dict[str, object]:
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


if HAS_BDD_RUNTIME and FEATURE_FILE.exists():
    scenarios(str(FEATURE_FILE))

    @pytest.fixture
    def context():
        return {}

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

    def _headers(rol: str) -> dict[str, str]:
        token = create_access_token(
            {
                "sub": str(uuid4()),
                "email": "usuario@condomanager.pe",
                "rol": rol,
                "condominio_id": None,
                "departamentos": [],
            }
        )
        return {"Authorization": f"Bearer {token}"}

    @given(parsers.parse('que existe un usuario autenticado con rol "{rol}"'))
    def usuario_autenticado(context, rol):
        context["headers"] = _headers(rol)

    @given("que la solicitud no tiene un Bearer Token")
    def solicitud_anonima(context):
        context["headers"] = {}

    @when(parsers.parse('registra un condominio válido llamado "{nombre}"'))
    @when(parsers.parse('intenta registrar un condominio válido llamado "{nombre}"'))
    def registrar_condominio(context, client, nombre):
        context["response"] = client.post(
            "/api/v1/condominios",
            json=_payload(nombre),
            headers=context["headers"],
        )

    @when("registra un condominio con regla porcentual sin tasa")
    def registrar_mora_invalida(context, client):
        datos = _payload()
        datos.update({"regla_mora_tipo": "PORCENTAJE_SALDO"})
        context["response"] = client.post(
            "/api/v1/condominios", json=datos, headers=context["headers"]
        )

    @when("consulta un UUID de condominio inexistente")
    def consultar_inexistente(context, client):
        context["response"] = client.get(
            f"/api/v1/condominios/{uuid4()}", headers=context["headers"]
        )

    @given(parsers.parse('están registrados "{norte}" y "{sur}"'))
    def registrar_dos_condominios(context, client, norte, sur):
        primero = client.post(
            "/api/v1/condominios", json=_payload(norte), headers=context["headers"]
        ).json()
        datos_sur = _payload(sur)
        datos_sur["moneda"] = "USD"
        segundo = client.post(
            "/api/v1/condominios", json=datos_sur, headers=context["headers"]
        ).json()
        context["creados"] = [primero, segundo]

    @when("consulta ambos condominios por sus UUID")
    def consultar_ambos(context, client):
        context["consultados"] = [
            client.get(
                f"/api/v1/condominios/{condominio['id']}",
                headers=context["headers"],
            ).json()
            for condominio in context["creados"]
        ]

    @when("lista los condominios activos")
    def listar_condominios_activos(context, client):
        context["response"] = client.get(
            "/api/v1/condominios",
            headers=context["headers"],
        )

    @then(parsers.parse("la API responde con código {codigo:d}"))
    def verificar_codigo(context, codigo):
        assert context["response"].status_code == codigo

    @then("el condominio queda activo con un UUID")
    def verificar_alta(context):
        data = context["response"].json()
        assert data["activo"] is True
        assert data["id"]

    @then(parsers.parse('se registra la auditoría "{accion}"'))
    def verificar_auditoria(repository, accion):
        assert repository.auditorias[-1].accion_ejecutada == accion

    @then("no se persiste ningún condominio")
    def verificar_sin_persistencia(repository):
        assert repository.condominios == {}

    @then(parsers.parse('el error es "{error_code}"'))
    def verificar_error(context, error_code):
        assert context["response"].json()["error_code"] == error_code

    @then("cada respuesta conserva su propia configuración")
    def verificar_aislamiento(context):
        norte, sur = context["consultados"]
        assert norte["id"] != sur["id"]
        assert norte["nombre"] == "Condominio Norte"
        assert norte["moneda"] == "PEN"
        assert sur["nombre"] == "Condominio Sur"
        assert sur["moneda"] == "USD"

    @then("obtiene ambos condominios como contextos seleccionables")
    def verificar_listado_seleccionable(context):
        assert context["response"].status_code == 200
        assert {item["id"] for item in context["response"].json()} == {
            item["id"] for item in context["creados"]
        }
else:

    def test_bdd_skipped_if_runtime_is_unavailable():
        pytest.skip("FastAPI o pytest-bdd no están disponibles en este entorno.")
