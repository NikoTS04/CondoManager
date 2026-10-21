"""Contrato ejecutable de CON-06 mediante las rutas y PostgreSQL reales."""

import asyncio
from pathlib import Path

from pytest_bdd import given, scenarios, then, when
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol
from src.tests.bdd.test_alta_usuarios_bdd import ingresar
from src.tests.integration.test_alta_usuarios_db import datos, otro_condominio

scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/05-usuarios-rbac/features/roles_permisos.feature"
    )
)


@given("un condominio con SuperAdmin y usuarios persistentes para roles", target_fixture="roles")
def contexto(cliente_usuarios):
    client, base = cliente_usuarios
    uid = id_demo("residente102@villabonita3.pe")
    return {
        "client": client,
        "base": base,
        "uid": uid,
        "ruta": f"/api/v1/condominios/{base.cid}/usuarios/{uid}/rol",
        "super": ingresar(client),
        "junta": ingresar(client, "admin@villabonita3.pe", "Admin123!"),
        "anterior": ingresar(client, "residente102@villabonita3.pe", "Residente123!"),
    }


@when("el SuperAdmin cambia un residente a Auditor")
def cambiar(roles):
    roles["resultado"] = roles["client"].put(
        roles["ruta"], headers=roles["super"], json={"rol": "AUDITOR"}
    )
    assert roles["resultado"].status_code == 200


@then("la sesión anterior queda revocada")
@then("el token anterior sigue revocado después de restaurar")
def revocada(roles):
    assert roles["client"].get("/api/v1/auth/me", headers=roles["anterior"]).status_code == 401


@then("un nuevo login obtiene el rol Auditor de solo lectura")
def auditor(roles):
    headers = ingresar(roles["client"], "residente102@villabonita3.pe", "Residente123!")
    assert roles["client"].get("/api/v1/auth/me", headers=headers).json()["rol"] == "AUDITOR"
    assert (
        roles["client"]
        .post(f"/api/v1/condominios/{roles['base'].cid}/usuarios", headers=headers, json=datos())
        .status_code
        == 403
    )


@when("la Junta intenta asignar Admin Junta a un residente")
def elevar(roles):
    roles["resultado"] = roles["client"].put(
        roles["ruta"], headers=roles["junta"], json={"rol": "ADMIN_JUNTA"}
    )


@then("el cambio de rol se rechaza sin modificar la asignación")
def rechazado(roles):
    assert roles["resultado"].status_code == 403
    assert roles["client"].get(roles["ruta"], headers=roles["super"]).json()["rol"] == "RESIDENTE"


@when("la Junta asigna Auditor a un residente")
def junta_asigna(roles):
    roles["resultado"] = roles["client"].put(
        roles["ruta"], headers=roles["junta"], json={"rol": "AUDITOR"}
    )
    assert roles["resultado"].status_code == 200


async def logs_y_usuario(roles):
    async with roles["base"].sessions() as db:
        logs = list(await db.scalars(select(AuditoriaLogORM)))
        usuario = await db.get(Usuario, roles["uid"])
        return logs, usuario


@then("el nuevo rol queda persistido y auditado")
def auditado(roles):
    assert roles["client"].get(roles["ruta"], headers=roles["super"]).json()["rol"] == "AUDITOR"
    logs, usuario = asyncio.run(logs_y_usuario(roles))
    assert usuario.auth_revision == 2
    assert len(logs) == 1 and logs[0].accion_ejecutada == "ROL_CAMBIADO"


@when("el SuperAdmin revoca y restaura el rol de un residente")
def restaurar(roles):
    assert roles["client"].delete(roles["ruta"], headers=roles["super"]).status_code == 200
    assert (
        roles["client"]
        .put(roles["ruta"], headers=roles["super"], json={"rol": "RESIDENTE"})
        .status_code
        == 200
    )


@then("se conserva la asignación y sus vínculos")
def conservar(roles):
    async def comprobar():
        async with roles["base"].sessions() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(UsuarioRol)
                    .where(UsuarioRol.usuario_id == roles["uid"])
                )
                == 1
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(UsuarioDepartamento)
                    .where(UsuarioDepartamento.usuario_id == roles["uid"])
                )
                == 1
            )

    asyncio.run(comprobar())


@when("se solicita dos veces el mismo cambio de rol")
def repetir(roles):
    cambiar(roles)
    cambiar(roles)


@then("se registra una sola modificación de permisos")
def unica(roles):
    logs, usuario = asyncio.run(logs_y_usuario(roles))
    assert len(logs) == 1 and usuario.auth_revision == 2


@when("la Junta solicita cambiar un rol en otro condominio")
def ajeno(roles):
    otro = asyncio.run(otro_condominio(roles["base"]))
    roles["resultado"] = roles["client"].put(
        f"/api/v1/condominios/{otro}/usuarios/{roles['uid']}/rol",
        headers=roles["junta"],
        json={"rol": "AUDITOR"},
    )


@when("se intenta asignar Propietario como rol")
def tenencia(roles):
    roles["resultado"] = roles["client"].put(
        roles["ruta"], headers=roles["super"], json={"rol": "PROPIETARIO"}
    )


@then("la API rechaza el cuerpo de rol inválido")
def invalido(roles):
    assert roles["resultado"].status_code == 422
    assert roles["resultado"].json()["error_code"] == "DATOS_ROL_INVALIDOS"
