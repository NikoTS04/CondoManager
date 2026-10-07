"""Pruebas de integración de las altas de catálogo: `/areas/crear` y `/departamentos/crear`.

Verifican la persistencia real en PostgreSQL (`areas_comunes` y `departamentos`) y los
códigos de error de los contratos documentados en `specs/05-api/api-contracts.md`.
"""

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


SALTA_SIN_FASTAPI = pytest.mark.skipif(
    not HAS_FASTAPI, reason="fastapi no está instalado en el entorno de pruebas actual"
)


@pytest.fixture
def condominio():
    """Condominio real creado vía API; se elimina (con sus áreas y departamentos) al terminar."""
    from src.tests.integration.db_pruebas import borrar_condominio, crear_condominio_de_prueba

    datos = crear_condominio_de_prueba(client, uuid.uuid4().hex[:8])
    yield datos
    borrar_condominio(datos["id"])


def _payload_area(condominio_id: str, **cambios):
    payload = {
        "condominio_id": condominio_id,
        "nombre": f"Salón Social {uuid.uuid4().hex[:6]}",
        "descripcion": "Salón social con acceso a terraza",
        "aforo_maximo": 40,
        "costo_reserva": "30.00",
    }
    payload.update(cambios)
    return payload


def _payload_departamento(condominio_id: str, **cambios):
    payload = {
        "condominio_id": condominio_id,
        "numero": uuid.uuid4().hex[:5].upper(),
        "piso": 3,
        "coeficiente_participacion": "0.7143",
    }
    payload.update(cambios)
    return payload


# ============================================================================
# POST /api/v1/areas/crear
# ============================================================================

@SALTA_SIN_FASTAPI
def test_crear_area_retorna_201_y_persiste_en_bd(condominio):
    payload = _payload_area(condominio["id"])
    res = client.post("/api/v1/areas/crear", json=payload)
    assert res.status_code == 201, res.text

    area = res.json()
    assert area["condominio_id"] == condominio["id"]
    assert area["nombre"] == payload["nombre"]
    assert area["aforo_maximo"] == 40
    assert area["costo_reserva"] == "30.00"
    assert area["esta_activa"] is True

    res_catalogo = client.get("/api/v1/areas")
    assert res_catalogo.status_code == 200
    assert any(a["id"] == area["id"] for a in res_catalogo.json())


@SALTA_SIN_FASTAPI
def test_crear_area_nombre_duplicado_retorna_409(condominio):
    payload = _payload_area(condominio["id"], nombre="Quincho Duplicado")
    assert client.post("/api/v1/areas/crear", json=payload).status_code == 201

    res_dup = client.post("/api/v1/areas/crear", json=payload)
    assert res_dup.status_code == 409
    assert res_dup.json()["detail"]["error_code"] == "AREA_DUPLICADA"


@SALTA_SIN_FASTAPI
def test_crear_area_condominio_inexistente_retorna_404():
    payload = _payload_area(str(uuid.uuid4()))
    res = client.post("/api/v1/areas/crear", json=payload)
    assert res.status_code == 404
    assert res.json()["detail"]["error_code"] == "CONDOMINIO_NO_ENCONTRADO"


@SALTA_SIN_FASTAPI
def test_crear_area_aforo_invalido_retorna_422(condominio):
    payload = _payload_area(condominio["id"], aforo_maximo=0)
    res = client.post("/api/v1/areas/crear", json=payload)
    assert res.status_code == 422


# ============================================================================
# POST /api/v1/departamentos/crear
# ============================================================================

@SALTA_SIN_FASTAPI
def test_crear_departamento_retorna_201_y_persiste_en_bd(condominio):
    payload = _payload_departamento(
        condominio["id"], numero="101-TEST", estado_financiero="EN_MORA"
    )
    res = client.post("/api/v1/departamentos/crear", json=payload)
    assert res.status_code == 201, res.text

    departamento = res.json()
    assert departamento["condominio_id"] == condominio["id"]
    assert departamento["numero"] == "101-TEST"
    assert departamento["piso"] == 3
    assert departamento["coeficiente_participacion"] == "0.7143"
    assert departamento["saldo_a_favor"] == "0.00"
    assert departamento["estado_financiero"] == "EN_MORA"


@SALTA_SIN_FASTAPI
def test_crear_departamento_duplicado_retorna_409(condominio):
    payload = _payload_departamento(condominio["id"], numero="DUP-1")
    assert client.post("/api/v1/departamentos/crear", json=payload).status_code == 201

    res_dup = client.post("/api/v1/departamentos/crear", json=payload)
    assert res_dup.status_code == 409
    assert res_dup.json()["detail"]["error_code"] == "DEPARTAMENTO_DUPLICADO"


@SALTA_SIN_FASTAPI
def test_crear_departamento_condominio_inexistente_retorna_404():
    payload = _payload_departamento(str(uuid.uuid4()))
    res = client.post("/api/v1/departamentos/crear", json=payload)
    assert res.status_code == 404
    assert res.json()["detail"]["error_code"] == "CONDOMINIO_NO_ENCONTRADO"


@SALTA_SIN_FASTAPI
def test_crear_departamento_coeficiente_invalido_retorna_422(condominio):
    payload = _payload_departamento(condominio["id"], coeficiente_participacion="0.0000")
    res = client.post("/api/v1/departamentos/crear", json=payload)
    assert res.status_code == 422


# ============================================================================
# Flujo combinado: lo que se crea con los POST es lo que consume la reserva
# ============================================================================

@SALTA_SIN_FASTAPI
def test_reserva_usa_departamento_en_mora_creado_por_api(condominio):
    res_area = client.post(
        "/api/v1/areas/crear", json=_payload_area(condominio["id"], nombre="Parrilla Morosa")
    )
    assert res_area.status_code == 201, res_area.text

    res_dpto = client.post(
        "/api/v1/departamentos/crear",
        json=_payload_departamento(
            condominio["id"],
            numero="999-MORA",
            estado_financiero="EN_MORA",
        ),
    )
    assert res_dpto.status_code == 201, res_dpto.text

    res_reserva = client.post(
        "/api/v1/reservas",
        json={
            "condominio_id": condominio["id"],
            "area_id": res_area.json()["id"],
            "departamento_id": res_dpto.json()["id"],
            "fecha_reserva": "2027-01-10",
            "hora_inicio": "10:00",
            "hora_fin": "12:00",
        },
    )
    assert res_reserva.status_code == 403
    assert res_reserva.json()["detail"]["error_code"] == "DEUDA_MORA_ACTIVA"
