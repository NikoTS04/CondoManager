"""BDD de CON-05 sobre endpoints y departamentos nuevos en PostgreSQL."""

import asyncio
from pathlib import Path

from pytest_bdd import given, scenarios, then, when

from src.modules.usuarios.demo import id_demo
from src.tests.bdd.test_alta_usuarios_bdd import ingresar
from src.tests.integration.test_alta_usuarios_db import otro_condominio
from src.tests.integration.test_vinculos_db import (
    TITULAR,
    A,
    B,
    logs_vinculos,
    ruta,
    solicitud_pago,
)

scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/05-usuarios-rbac/features/vinculos_departamentos.feature"
    )
)


def nueva_unidad(client, cid, headers, numero):
    edificio = client.post(
        f"/api/v1/condominios/{cid}/edificios",
        headers=headers,
        json={"nombre_bloque": "Bloque " + numero, "total_pisos": 2},
    )
    assert edificio.status_code == 201
    unidad = client.post(
        f"/api/v1/condominios/{cid}/edificios/{edificio.json()['id']}/departamentos",
        headers=headers,
        json={"numero": numero, "piso": 1, "coeficiente_participacion": "1.0000"},
    )
    assert unidad.status_code == 201
    return unidad.json()["id"]


@given("una administración y usuarios con unidades reales para vincular", target_fixture="vinculos")
def contexto(cliente_usuarios):
    client, base = cliente_usuarios
    admin = ingresar(client)
    return {
        "client": client,
        "base": base,
        "admin": admin,
        "unidades": [
            nueva_unidad(client, base.cid, admin, "BDD-1"),
            nueva_unidad(client, base.cid, admin, "BDD-2"),
        ],
    }


def asignar(caso, email=A, unidad=0, relacion=TITULAR):
    return caso["client"].put(
        ruta(caso, email, unidad), headers=caso["admin"], json={"tipo_relacion": relacion}
    )


@when("la administración registra un titular y un inquilino con varias unidades")
def mixto(vinculos):
    assert asignar(vinculos).status_code == 200
    assert asignar(vinculos, B, 1).status_code == 200
    assert asignar(vinculos, A, 1, "INQUILINO").status_code == 200


@then("el nuevo login representa las relaciones mixtas persistidas")
def login_mixto(vinculos):
    token = ingresar(vinculos["client"], A, "Residente123!")
    vinculos["residente"] = token
    perfil = vinculos["client"].get("/api/v1/auth/me", headers=token).json()
    relaciones = {v["departamento_id"]: v["tipo_relacion"] for v in perfil["departamentos"]}
    assert relaciones[vinculos["unidades"][0]] == TITULAR
    assert relaciones[vinculos["unidades"][1]] == "INQUILINO"


@then("el portal devuelve únicamente sus unidades activas reales")
def portal(vinculos):
    response = vinculos["client"].get("/api/v1/cuotas/departamentos", headers=vinculos["residente"])
    assert response.status_code == 200
    ids = {d["id"] for d in response.json()}
    perfil = vinculos["client"].get("/api/v1/auth/me", headers=vinculos["residente"]).json()
    assert ids == {v["departamento_id"] for v in perfil["departamentos"] if v["es_activo"]}
    assert set(vinculos["unidades"]) <= ids


@when("la administración intenta desactivar al último titular")
def retirar_titular(vinculos):
    assert asignar(vinculos).status_code == 200
    vinculos["resultado"] = vinculos["client"].delete(ruta(vinculos), headers=vinculos["admin"])


@then("la API exige un titular sin modificar el vínculo")
def titular_conservado(vinculos):
    assert vinculos["resultado"].status_code == 409
    assert vinculos["resultado"].json()["error_code"] == "TITULAR_REQUERIDO"
    relaciones = (
        vinculos["client"].get(ruta(vinculos, unidad=None), headers=vinculos["admin"]).json()
    )
    assert next(v for v in relaciones if v["departamento_id"] == vinculos["unidades"][0])[
        "es_activo"
    ]


@when("se intenta registrar un inquilino en una unidad sin titular")
def inquilino_sin_titular(vinculos):
    vinculos["resultado"] = asignar(vinculos, relacion="INQUILINO")


@then("la API exige un titular sin crear el vínculo")
def no_creado(vinculos):
    assert vinculos["resultado"].status_code == 409
    assert vinculos["resultado"].json()["error_code"] == "TITULAR_REQUERIDO"
    assert asyncio.run(logs_vinculos(vinculos["base"])) == []


@when("la administración revoca el vínculo de un inquilino")
def revocar(vinculos):
    assert asignar(vinculos).status_code == 200
    assert asignar(vinculos, B, relacion="INQUILINO").status_code == 200
    vinculos["anterior"] = ingresar(vinculos["client"], B, "Inquilino123!")
    assert (
        vinculos["client"].delete(ruta(vinculos, B), headers=vinculos["admin"]).status_code == 200
    )


@then("la sesión anterior queda revocada por el cambio de vínculo")
def sesion_revocada(vinculos):
    assert (
        vinculos["client"].get("/api/v1/auth/me", headers=vinculos["anterior"]).status_code == 401
    )


@then("un nuevo login no permite operar sobre la unidad desvinculada")
def unidad_revocada(vinculos):
    nuevo = ingresar(vinculos["client"], B, "Inquilino123!")
    assert (
        vinculos["client"]
        .post(
            "/api/v1/pagos/reportar",
            headers=nuevo,
            data=solicitud_pago(vinculos["unidades"][0]),
            files={"archivo_voucher": ("voucher.png", b"sin-acceso", "image/png")},
        )
        .status_code
        == 403
    )


@when("un Auditor intenta vincular un usuario")
def auditor(vinculos):
    actor = ingresar(vinculos["client"], "auditor@villabonita3.pe", "Auditor123!")
    vinculos["resultado"] = vinculos["client"].put(
        ruta(vinculos), headers=actor, json={"tipo_relacion": TITULAR}
    )


@then("la API rechaza la vinculación por falta de permisos")
def denegado(vinculos):
    assert vinculos["resultado"].status_code == 403


@when("se intenta vincular una unidad de otro condominio")
def unidad_ajena(vinculos):
    otro = asyncio.run(otro_condominio(vinculos["base"]))
    did = nueva_unidad(vinculos["client"], otro, vinculos["admin"], "AJENA")
    vinculos["resultado"] = vinculos["client"].put(
        ruta(vinculos).rsplit("/", 1)[0] + "/" + did,
        headers=vinculos["admin"],
        json={"tipo_relacion": TITULAR},
    )


@then("la API no encuentra la unidad en el contexto solicitado")
def no_encontrado(vinculos):
    assert vinculos["resultado"].status_code == 404
    assert vinculos["resultado"].json()["error_code"] == "DEPARTAMENTO_NO_ENCONTRADO"


@when("se solicita dos veces el mismo vínculo")
def repetir(vinculos):
    assert asignar(vinculos).status_code == 200
    assert asignar(vinculos).status_code == 200


@then("existe una sola relación y un solo cambio auditado")
def unica(vinculos):
    relaciones = (
        vinculos["client"].get(ruta(vinculos, unidad=None), headers=vinculos["admin"]).json()
    )
    assert sum(v["departamento_id"] == vinculos["unidades"][0] for v in relaciones) == 1
    logs = asyncio.run(logs_vinculos(vinculos["base"]))
    assert len(logs) == 1 and logs[0].actor_id == str(id_demo("superadmin@condomanager.pe"))
