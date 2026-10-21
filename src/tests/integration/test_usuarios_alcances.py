"""Sesión v2 y aislamiento real de los recursos piloto por rol, contexto y vínculo."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.security import create_access_token, decode_access_token
from src.main import app
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, vinculo_piloto
from src.tests import reservas_contrato as notificaciones
from src.tests import reservas_contrato as reservas

pytestmark = pytest.mark.usefixtures(
    "autorizacion_aislada", "identidad_piloto", "finanzas_contrato"
)

client = TestClient(app)
CID = str(CONDOMINIO_PILOTO_ID)
AREA = "11111111-1111-1111-1111-111111111101"


def unidad(numero):
    return vinculo_piloto(numero, "PROPIETARIO_TITULAR")["departamento_id"]


def auth(rol="RESIDENTE", numeros=("102",), cid=CID, vinculos=None):
    return {
        "Authorization": "Bearer "
        + create_access_token(
            {
                "sub": "prueba",
                "rol": rol,
                "condominio_id": cid,
                "departamentos": vinculos
                if vinculos is not None
                else [vinculo_piloto(n, "PROPIETARIO_TITULAR") for n in numeros],
            }
        )
    }


def solicitud_reserva(numero="102", **extras):
    return {
        "condominio_id": CID,
        "area_id": AREA,
        "departamento_id": unidad(numero),
        "fecha_reserva": (date.today() + timedelta(days=10)).isoformat(),
        "hora_inicio": "14:00",
        "hora_fin": "16:00",
        **extras,
    }


def solicitud_pago(numero="102"):
    return {
        "departamento_id": unidad(numero),
        "banco": "YAPE",
        "numero_operacion": "OP-" + uuid4().hex,
        "fecha_operacion": "2026-10-15",
        "monto": "150.00",
        "url_voucher": "https://ejemplo.test/voucher.jpg",
    }


@pytest.fixture(autouse=True)
def aislar_recursos(monkeypatch, finanzas_contrato):
    monkeypatch.setattr(reservas, "RESERVAS_REGISTRADAS", {})
    monkeypatch.setattr(notificaciones, "NOTIFICACIONES_REGISTRADAS", {})


def test_login_me_y_demo_comparten_perfil_y_nombres_completos():
    data = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inquilino504@villabonita3.pe",
            "password": "Inquilino123!",
        },
    ).json()
    perfil = data["usuario"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + data["access_token"]})
    demo = client.get("/api/v1/auth/demo-users").json()
    assert me.status_code == 200
    assert me.json() == perfil == next(u for u in demo if u["email"] == perfil["email"])
    assert perfil["rol"] == "RESIDENTE"
    assert perfil["apellido"] == "Fernández"
    assert perfil["departamentos"][0]["tipo_relacion"] == "INQUILINO"


@pytest.mark.parametrize(
    "ruta",
    [
        "/cuotas/departamentos",
        "/areas",
        "/reservas",
        "/pagos/comprobantes",
        "/notificaciones/logs",
    ],
)
def test_consultas_sin_autenticacion_rechazadas(ruta):
    assert client.get("/api/v1" + ruta).status_code == 401


def test_sesion_con_relaciones_mixtas_solo_ve_sus_vinculos_activos(monkeypatch, identidad_piloto):
    origen = identidad_piloto.perfiles["residente102@villabonita3.pe"]
    datos = {
        **origen,
        "departamentos": [
            vinculo_piloto("102", "PROPIETARIO_TITULAR"),
            vinculo_piloto("504", "INQUILINO"),
            vinculo_piloto("302", "COPROPIETARIO", es_activo=False),
        ],
    }
    monkeypatch.setitem(identidad_piloto.perfiles, origen["email"], datos)
    session = client.post(
        "/api/v1/auth/login",
        json={
            "email": origen["email"],
            "password": "Residente123!",
        },
    ).json()
    claims = decode_access_token(session["access_token"])
    assert claims["departamentos"] == session["usuario"]["departamentos"]
    headers = {"Authorization": "Bearer " + session["access_token"]}
    unidades = client.get("/api/v1/cuotas/departamentos", headers=headers).json()
    assert {d["id"] for d in unidades} == {unidad("102"), unidad("504")}
    for numero in ("102", "504"):
        assert (
            client.post(
                "/api/v1/pagos/reportar", headers=headers, json=solicitud_pago(numero)
            ).status_code
            == 202
        )
    for numero in ("302", "402"):
        assert (
            client.post(
                "/api/v1/pagos/reportar", headers=headers, json=solicitud_pago(numero)
            ).status_code
            == 403
        )


def test_pago_y_reserva_ajenos_no_se_registran(finanzas_contrato):
    for ruta, body in (
        ("/pagos/reportar", solicitud_pago("504")),
        ("/reservas", solicitud_reserva("504")),
    ):
        assert client.post("/api/v1" + ruta, headers=auth(), json=body).status_code == 403
    assert not finanzas_contrato.comprobantes
    assert not reservas.RESERVAS_REGISTRADAS


def test_listas_privadas_y_calendario_sin_unidad_ajena():
    own = client.post("/api/v1/reservas", headers=auth(), json=solicitud_reserva()).json()
    assert client.get("/api/v1/reservas", headers=auth(numeros=("504",))).json() == []
    disponible = client.get(
        f"/api/v1/areas/{AREA}/disponibilidad",
        headers=auth(numeros=("504",)),
        params={"fecha": own["fecha_reserva"]},
    )
    assert disponible.status_code == 200
    assert disponible.json() == [{"hora_inicio": "14:00:00", "hora_fin": "16:00:00"}]
    pago = solicitud_pago()
    assert client.post("/api/v1/pagos/reportar", headers=auth(), json=pago).status_code == 202
    assert client.get("/api/v1/pagos/comprobantes", headers=auth(numeros=("504",))).json() == []
    assert len(client.get("/api/v1/pagos/comprobantes", headers=auth()).json()) == 1
    ajeno = {**pago, "departamento_id": unidad("504")}
    assert (
        client.post(
            "/api/v1/pagos/reportar", headers=auth(numeros=("504",)), json=ajeno
        ).status_code
        == 409
    )


def test_cancelar_reserva_ajena_y_suplantar_admin_no_es_posible():
    response = client.post("/api/v1/reservas", headers=auth(), json=solicitud_reserva())
    assert response.status_code == 201
    rid = response.json()["id"]
    ruta = f"/api/v1/reservas/{rid}/cancelar"
    assert (
        client.post(ruta, headers=auth(numeros=("504",)), json={"es_admin": True}).status_code
        == 403
    )
    registro = reservas.RESERVAS_REGISTRADAS[next(iter(reservas.RESERVAS_REGISTRADAS))]
    registro["fecha_reserva"] = datetime.now(UTC).date()
    assert client.post(ruta, headers=auth(), json={"es_admin": True}).status_code == 422
    assert registro["estado"] == "CONFIRMADA"
    assert (
        client.post(ruta, headers=auth("ADMIN_JUNTA"), json={"es_admin": False}).status_code == 200
    )


def test_cancelacion_residente_anticipada_y_mora_por_unidad():
    headers = auth(numeros=("102", "402"))
    moroso = client.post("/api/v1/reservas", headers=headers, json=solicitud_reserva("402"))
    assert (
        moroso.status_code == 403 and moroso.json()["detail"]["error_code"] == "DEUDA_MORA_ACTIVA"
    )
    propia = client.post("/api/v1/reservas", headers=headers, json=solicitud_reserva())
    assert propia.status_code == 201
    assert (
        client.post(f"/api/v1/reservas/{propia.json()['id']}/cancelar", headers=headers).status_code
        == 200
    )


@pytest.mark.parametrize("rol", ["AUDITOR", "RESIDENTE"])
def test_roles_no_administrativos_no_mutan_recursos(rol):
    headers = auth(rol)
    for ruta, body in (
        ("/pagos/" + str(uuid4()) + "/conciliar", {"decision": "APROBADO"}),
        ("/moras/evaluar", {"condominio_id": CID}),
        (
            "/notificaciones/comunicado-masivo",
            {
                "condominio_id": CID,
                "titulo": "Aviso general",
                "mensaje": "Mensaje para los residentes.",
            },
        ),
    ):
        assert client.post("/api/v1" + ruta, headers=headers, json=body).status_code == 403
    if rol == "AUDITOR":
        assert client.get("/api/v1/pagos/comprobantes", headers=headers).status_code == 200
        assert client.get("/api/v1/notificaciones/logs", headers=headers).status_code == 200
        assert (
            client.post(
                "/api/v1/pagos/reportar", headers=headers, json=solicitud_pago()
            ).status_code
            == 403
        )
        assert (
            client.post("/api/v1/reservas", headers=headers, json=solicitud_reserva()).status_code
            == 403
        )


@pytest.mark.parametrize("rol", ["ADMIN_JUNTA", "AUDITOR", "RESIDENTE"])
def test_condominio_ajeno_rechazado_en_consultas_y_mutaciones(rol):
    otro = str(uuid4())
    headers = auth(rol, cid=otro)
    assert (
        client.get(
            "/api/v1/cuotas/departamentos", headers=headers, params={"condominio_id": CID}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/reservas", headers=headers, json=solicitud_reserva()).status_code
        == 403
    )
    assert (
        client.post("/api/v1/pagos/reportar", headers=headers, json=solicitud_pago()).status_code
        == 403
    )


def test_recurso_inexistente_no_se_asume_solvente():
    payload = solicitud_reserva(departamento_id=str(uuid4()))
    assert (
        client.post("/api/v1/reservas", headers=auth("SUPERADMIN"), json=payload).status_code == 404
    )
