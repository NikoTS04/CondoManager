"""Aceptación ejecutable de CON-76/7 sobre la API y PostgreSQL."""

import asyncio
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import select

from src.core.config import settings
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioDepartamento
from src.tests.bdd.test_alta_usuarios_bdd import ingresar
from src.tests.integration.test_identidad_sprint3_db import PASSWORD, datos, token_invitacion

scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/05-usuarios-rbac/features/invitacion_relevo.feature"
    )
)


@given("una invitación pendiente en un condominio activo", target_fixture="caso")
def invitacion(cliente_usuarios, monkeypatch):
    client, base = cliente_usuarios
    monkeypatch.setattr(settings, "IDENTITY_DELIVERY_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ACTIVACION_WEB_URL", "https://condo.ejemplo.test/activar")
    headers = {**ingresar(client), "Idempotency-Key": str(uuid4())}
    response = client.post(
        f"/api/v1/condominios/{base.cid}/invitaciones", headers=headers, json=datos()
    )
    assert response.status_code == 201, response.text
    return {
        "client": client,
        "base": base,
        "token": asyncio.run(token_invitacion(base, response.json()["id"])),
    }


@when("el usuario activa con su token y contraseña")
def activar(caso):
    response = caso["client"].post(
        "/api/v1/auth/activar", json={"token": caso["token"], "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


@then("puede iniciar sesión con la contraseña elegida")
def acceso(caso):
    assert ingresar(caso["client"], datos()["email"], PASSWORD)


@then("reutilizar el token es rechazado")
def reutilizacion(caso):
    response = caso["client"].post(
        "/api/v1/auth/activar", json={"token": caso["token"], "password": PASSWORD}
    )
    assert response.status_code == 409


@given("un inquilino con sesión y un reemplazo autorizado", target_fixture="caso")
def inquilino(cliente_usuarios):
    client, base = cliente_usuarios
    saliente = id_demo("inquilino504@villabonita3.pe")
    entrante = id_demo("residente102@villabonita3.pe")

    async def preparar():
        async with base.sessions() as db, db.begin():
            vinculo = await db.scalar(
                select(UsuarioDepartamento).where(UsuarioDepartamento.usuario_id == saliente)
            )
            db.add(
                UsuarioDepartamento(
                    usuario_id=id_demo("moroso402@villabonita3.pe"),
                    departamento_id=vinculo.departamento_id,
                    tipo_relacion="PROPIETARIO_TITULAR",
                    es_activo=True,
                )
            )
            return vinculo.id, vinculo.departamento_id

    vid, did = asyncio.run(preparar())
    return {
        "client": client,
        "base": base,
        "vid": vid,
        "anterior": ingresar(client, "inquilino504@villabonita3.pe", "Inquilino123!"),
        "headers": {**ingresar(client), "Idempotency-Key": str(uuid4())},
        "body": {
            "tipo": "INQUILINO",
            "saliente_id": str(saliente),
            "entrante_id": str(entrante),
            "departamento_id": str(did),
        },
    }


@when("la administración confirma el relevo")
def relevar(caso):
    caso["url"] = f"/api/v1/condominios/{caso['base'].cid}/relevos"
    r = caso["client"].post(caso["url"], headers=caso["headers"], json=caso["body"])
    assert r.status_code == 200, r.text
    caso["respuesta"] = r.json()


@then("la sesión anterior pierde acceso y el historial permanece")
def revocacion(caso):
    assert caso["client"].get("/api/v1/auth/me", headers=caso["anterior"]).status_code == 401

    async def verificar():
        async with caso["base"].sessions() as db:
            vinculo = await db.get(UsuarioDepartamento, caso["vid"])
            assert vinculo is not None and not vinculo.es_activo

    asyncio.run(verificar())


@then("ambos avisos quedan en la cola durable sin duplicarse")
def avisos(caso):
    assert (
        caso["client"].post(caso["url"], headers=caso["headers"], json=caso["body"]).json()
        == caso["respuesta"]
    )

    async def verificar():
        async with caso["base"].sessions() as db:
            avisos = list(await db.scalars(select(Notificacion)))
            assert len(avisos) == 2 and all(n.estado == "EN_COLA" for n in avisos)
        while await procesar_uno(caso["base"].sessions):
            pass
        async with caso["base"].sessions() as db:
            assert not (await db.get(UsuarioDepartamento, caso["vid"])).es_activo

    asyncio.run(verificar())
