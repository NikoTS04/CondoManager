"""Pruebas de integración de los endpoints PROC-05: /usuario/crear, /usuario/roles y /condominio/crear.

La sesión de base de datos se sustituye mediante dependency_overrides por un fake asincrono,
de modo que las pruebas son deterministas y no requieren PostgreSQL levantado.
"""

import uuid
from datetime import UTC, datetime

import pytest

try:
    from fastapi.testclient import TestClient

    from src.core.database import get_db_session
    from src.main import app
    from src.modules.condominios.models import Condominio
    from src.modules.usuarios.models import Usuario, UsuarioRol

    client = TestClient(app)
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    client = None


SALTA_SIN_FASTAPI = pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)


class _ResultadoFake:
    def __init__(self, valor):
        self._valor = valor

    def scalar_one_or_none(self):
        return self._valor


class SesiónFake:
    """Sesión asíncrona mínima que replica el ciclo add/flush/execute de SQLAlchemy."""

    def __init__(self, *, usuario_existente=None, condominio_existente=None, rol_existente=None):
        self.usuario_existente = usuario_existente
        self.condominio_existente = condominio_existente
        self.rol_existente = rol_existente
        self.agregados = []

    def add(self, objeto):
        self.agregados.append(objeto)

    async def flush(self):
        for objeto in self.agregados:
            if getattr(objeto, "id", None) is None:
                objeto.id = uuid.uuid4()
            if hasattr(objeto, "creado_en") and getattr(objeto, "creado_en", None) is None:
                objeto.creado_en = datetime.now(UTC)

    async def commit(self):
        """Los endpoints confirman la transacción antes de responder (no-op en la sesión fake)."""

    async def execute(self, stmt):
        entidad = stmt.column_descriptions[0]["entity"]
        if entidad is Usuario:
            return _ResultadoFake(self.usuario_existente)
        if entidad is Condominio:
            return _ResultadoFake(self.condominio_existente)
        if entidad is UsuarioRol:
            return _ResultadoFake(self.rol_existente)
        raise AssertionError(f"Consulta no soportada por la sesión fake: {stmt}")


@pytest.fixture
def sesión():
    return SesiónFake()


@pytest.fixture
def cliente(sesión):
    async def _override():
        yield sesión

    app.dependency_overrides[get_db_session] = _override
    with client:
        yield client
    app.dependency_overrides.clear()


@SALTA_SIN_FASTAPI
def test_las_tres_rutas_estan_registradas():
    rutas = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/usuario/crear" in rutas
    assert "/api/v1/usuario/roles" in rutas
    assert "/api/v1/condominio/crear" in rutas


@SALTA_SIN_FASTAPI
def test_crear_usuario_retorna_201_sin_exponer_password(cliente, sesión):
    payload = {
        "email": "Residente101@Gmail.com",
        "password": "claveSegura123",
        "nombre": "María",
        "apellido": "Flores",
        "documento_identidad": "74125896",
        "telefono": "987654321",
    }
    response = cliente.post("/api/v1/usuario/crear", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "residente101@gmail.com"
    assert body["esta_activo"] is True
    assert "password" not in body and "password_hash" not in body
    assert len(sesión.agregados) == 1
    assert sesión.agregados[0].password_hash != payload["password"]


@SALTA_SIN_FASTAPI
def test_crear_usuario_email_duplicado_retorna_409(cliente, sesión):
    sesión.usuario_existente = Usuario(
        id=uuid.uuid4(),
        email="residente101@gmail.com",
        password_hash="x",
        nombre="María",
        apellido="Flores",
        documento_identidad="74125896",
    )
    response = cliente.post(
        "/api/v1/usuario/crear",
        json={
            "email": "residente101@gmail.com",
            "password": "claveSegura123",
            "nombre": "María",
            "apellido": "Flores",
            "documento_identidad": "74125896",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "EMAIL_YA_REGISTRADO"


@SALTA_SIN_FASTAPI
def test_crear_usuario_valida_longitud_de_password(cliente):
    response = cliente.post(
        "/api/v1/usuario/crear",
        json={
            "email": "nuevo@gmail.com",
            "password": "corta",
            "nombre": "Ana",
            "apellido": "Pérez",
            "documento_identidad": "45678912",
        },
    )
    assert response.status_code == 422


@SALTA_SIN_FASTAPI
def test_asignar_rol_retorna_201(cliente, sesión):
    usuario_id = uuid.uuid4()
    condominio_id = uuid.uuid4()
    sesión.usuario_existente = Usuario(
        id=usuario_id,
        email="residente101@gmail.com",
        password_hash="x",
        nombre="María",
        apellido="Flores",
        documento_identidad="74125896",
    )
    sesión.condominio_existente = Condominio(
        id=condominio_id,
        nombre="Villa Bonita 3",
        direccion="Av. Los Rosales 245",
    )

    response = cliente.post(
        "/api/v1/usuario/roles",
        json={
            "usuario_id": str(usuario_id),
            "condominio_id": str(condominio_id),
            "rol": "RESIDENTE",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rol"] == "RESIDENTE"
    assert body["usuario_id"] == str(usuario_id)
    assert body["condominio_id"] == str(condominio_id)


@SALTA_SIN_FASTAPI
def test_asignar_rol_sin_usuario_retorna_404(cliente, sesión):
    sesión.condominio_existente = Condominio(
        id=uuid.uuid4(),
        nombre="Villa Bonita 3",
        direccion="Av. Los Rosales 245",
    )
    response = cliente.post(
        "/api/v1/usuario/roles",
        json={
            "usuario_id": str(uuid.uuid4()),
            "condominio_id": str(uuid.uuid4()),
            "rol": "ADMIN_JUNTA",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "USUARIO_NO_ENCONTRADO"


@SALTA_SIN_FASTAPI
def test_asignar_rol_sin_condominio_retorna_404(cliente, sesión):
    sesión.usuario_existente = Usuario(
        id=uuid.uuid4(),
        email="residente101@gmail.com",
        password_hash="x",
        nombre="María",
        apellido="Flores",
        documento_identidad="74125896",
    )
    response = cliente.post(
        "/api/v1/usuario/roles",
        json={
            "usuario_id": str(uuid.uuid4()),
            "condominio_id": str(uuid.uuid4()),
            "rol": "AUDITOR",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "CONDOMINIO_NO_ENCONTRADO"


@SALTA_SIN_FASTAPI
def test_asignar_rol_duplicado_retorna_409(cliente, sesión):
    sesión.usuario_existente = Usuario(
        id=uuid.uuid4(),
        email="residente101@gmail.com",
        password_hash="x",
        nombre="María",
        apellido="Flores",
        documento_identidad="74125896",
    )
    sesión.condominio_existente = Condominio(
        id=uuid.uuid4(),
        nombre="Villa Bonita 3",
        direccion="Av. Los Rosales 245",
    )
    sesión.rol_existente = UsuarioRol(
        id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        condominio_id=uuid.uuid4(),
        rol="RESIDENTE",
    )

    response = cliente.post(
        "/api/v1/usuario/roles",
        json={
            "usuario_id": str(uuid.uuid4()),
            "condominio_id": str(uuid.uuid4()),
            "rol": "RESIDENTE",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "ROL_YA_ASIGNADO"


@SALTA_SIN_FASTAPI
def test_asignar_rol_rechaza_rol_fuera_de_la_matriz_rbac(cliente):
    response = cliente.post(
        "/api/v1/usuario/roles",
        json={
            "usuario_id": str(uuid.uuid4()),
            "condominio_id": str(uuid.uuid4()),
            "rol": "GERENTE",
        },
    )
    assert response.status_code == 422


@SALTA_SIN_FASTAPI
def test_crear_condominio_retorna_201_con_configuracion_por_defecto(cliente, sesión):
    payload = {
        "nombre": "Villa Bonita 3",
        "direccion": "Av. Los Rosales 245, Lima",
        "moneda": "PEN",
        "regla_mora_tipo": "MONTO_FIJO",
        "monto_mora_fijo": "25",
        "dias_corte": 20,
        "dias_gracia": 2,
    }
    response = cliente.post("/api/v1/condominio/crear", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["nombre"] == "Villa Bonita 3"
    assert body["moneda"] == "PEN"
    assert body["monto_mora_fijo"] == "25.00"
    assert body["dias_corte"] == 20
    assert body["dias_gracia"] == 2
    assert len(sesión.agregados) == 1


@SALTA_SIN_FASTAPI
def test_crear_condominio_regla_monto_fijo_incoherente_retorna_422(cliente):
    response = cliente.post(
        "/api/v1/condominio/crear",
        json={
            "nombre": "Conjunto Los Cerezos",
            "direccion": "Jr. Las Orquídeas 120",
            "regla_mora_tipo": "MONTO_FIJO",
            "monto_mora_fijo": None,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "CONFIGURACION_MORA_INVALIDA"


@SALTA_SIN_FASTAPI
def test_crear_condominio_valida_limites_de_dias_de_corte(cliente):
    response = cliente.post(
        "/api/v1/condominio/crear",
        json={
            "nombre": "Conjunto Los Cerezos",
            "direccion": "Jr. Las Orquídeas 120",
            "dias_corte": 31,
        },
    )
    assert response.status_code == 422
