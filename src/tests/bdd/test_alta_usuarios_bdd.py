"""Escenarios CON-04 ejecutables contra PostgreSQL y las API reales."""

import asyncio
from pathlib import Path

from pytest_bdd import given, scenarios, then, when
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.tests.integration.test_alta_usuarios_db import PASSWORD, datos

scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/05-usuarios-rbac/features/alta_usuarios.feature"
    )
)


def ingresar(client, email="superadmin@condomanager.pe", password="SuperAdmin123!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@given("un condominio y un SuperAdmin persistentes", target_fixture="caso")
def contexto(cliente_usuarios):
    client, base = cliente_usuarios
    return {"client": client, "base": base, "super": ingresar(client)}


@when("registra un usuario con contraseña inicial")
def alta(caso):
    response = caso["client"].post(
        f"/api/v1/condominios/{caso['base'].cid}/usuarios", headers=caso["super"], json=datos()
    )
    assert response.status_code == 201, response.text
    caso["cuenta"] = response.json()


@then("la cuenta queda inactiva y no puede iniciar sesión")
def inactivo(caso):
    assert caso["cuenta"]["esta_activo"] is False
    assert (
        caso["client"]
        .post("/api/v1/auth/login", json={"email": datos()["email"], "password": PASSWORD})
        .status_code
        == 401
    )


def activar(caso, activo=True, actor=None):
    return caso["client"].patch(
        f"/api/v1/usuarios/{caso['cuenta']['id']}/estado",
        params={"condominio_id": caso["base"].cid},
        headers=actor or caso["super"],
        json={"esta_activo": activo},
    )


@when("el SuperAdmin activa la cuenta")
def habilitar(caso):
    assert activar(caso).status_code == 200


@then("el usuario inicia sesión con sus credenciales persistidas")
def login_persistente(caso):
    headers = ingresar(caso["client"], datos()["email"], PASSWORD)
    perfil = caso["client"].get("/api/v1/auth/me", headers=headers)
    assert perfil.status_code == 200 and perfil.json()["id"] == caso["cuenta"]["id"]


@given("un usuario activo con una sesión abierta")
def sesion(caso):
    alta(caso)
    habilitar(caso)
    caso["anterior"] = ingresar(caso["client"], datos()["email"], PASSWORD)


@when("el SuperAdmin desactiva y reactiva la cuenta")
def revocar(caso):
    assert activar(caso, False).status_code == 200
    assert activar(caso, True).status_code == 200


@then("el token anterior es rechazado y un nuevo login funciona")
def comprobar_revocacion(caso):
    assert caso["client"].get("/api/v1/auth/me", headers=caso["anterior"]).status_code == 401
    login_persistente(caso)


@given("un usuario registrado por un administrador de junta")
def alta_junta(caso):
    caso["junta"] = ingresar(caso["client"], "admin@villabonita3.pe", "Admin123!")
    response = caso["client"].post(
        f"/api/v1/condominios/{caso['base'].cid}/usuarios", headers=caso["junta"], json=datos()
    )
    assert response.status_code == 201
    caso["cuenta"] = response.json()


@when("el administrador de junta intenta activar la cuenta")
def junta_activa(caso):
    caso["resultado"] = activar(caso, actor=caso["junta"])


@then("la API rechaza el cambio y conserva la cuenta inactiva")
def denegado(caso):
    assert caso["resultado"].status_code == 403
    inactivo(caso)


@then("repetir el correo o documento normalizado no crea otra identidad")
def duplicados(caso):
    ruta = f"/api/v1/condominios/{caso['base'].cid}/usuarios"
    for body in (
        datos(email=" NUEVO@EJEMPLO.TEST "),
        datos(email="otro@ejemplo.test", documento_identidad=" abc12345 "),
    ):
        assert caso["client"].post(ruta, headers=caso["super"], json=body).status_code == 409


@then("un administrador de otro condominio no consulta ni crea usuarios en este contexto")
def contexto_ajeno(caso):
    from src.tests.integration.test_alta_usuarios_db import otro_condominio

    otro = asyncio.run(otro_condominio(caso["base"]))
    junta = ingresar(caso["client"], "admin@villabonita3.pe", "Admin123!")
    ruta = f"/api/v1/condominios/{otro}/usuarios"
    assert caso["client"].get(ruta, headers=junta).status_code == 403
    assert caso["client"].post(ruta, headers=junta, json=datos()).status_code == 403


@when("el SuperAdmin solicita dos veces la activación")
def repetir(caso):
    habilitar(caso)
    habilitar(caso)


@then("solo un cambio de estado queda auditado")
def una_auditoria(caso):
    async def contar():
        async with caso["base"].sessions() as db:
            return await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "USUARIO_ESTADO_CAMBIADO")
            )

    assert asyncio.run(contar()) == 1
