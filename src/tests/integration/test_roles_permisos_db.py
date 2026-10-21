"""CON-06: autorización, sesiones, auditoría y concurrencia en PostgreSQL real."""

import asyncio
from importlib import import_module
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text

from scripts.seed_usuarios_demo import cargar_demo
from src.core.models_audit import AuditoriaLogORM
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository
from src.tests.integration.test_alta_usuarios_db import datos, login, otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
RESIDENTE = "residente102@villabonita3.pe"
JUNTA = "admin@villabonita3.pe"


def ruta(base, email=RESIDENTE, cid=None):
    return f"/api/v1/condominios/{cid or base.cid}/usuarios/{id_demo(email)}/rol"


async def test_cambio_de_rol_login_permisos_y_revocacion(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    anterior = await login(client, RESIDENTE, "Residente123!")
    response = await client.put(ruta(base), headers=admin, json={"rol": "AUDITOR"})
    assert response.status_code == 200
    assert response.json() == {
        "usuario_id": str(id_demo(RESIDENTE)),
        "condominio_id": base.cid,
        "rol": "AUDITOR",
        "es_activo": True,
    }
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401
    nuevo = await login(client, RESIDENTE, "Residente123!")
    assert (await client.get("/api/v1/auth/me", headers=nuevo)).json()["rol"] == "AUDITOR"
    assert (
        await client.get(f"/api/v1/condominios/{base.cid}/edificios", headers=nuevo)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/condominios/{base.cid}/usuarios", headers=nuevo, json=datos())
    ).status_code == 403
    # Volver al rol anterior no revive la sesión anterior.
    await client.put(ruta(base), headers=admin, json={"rol": "RESIDENTE"})
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401


async def test_asignar_rol_no_habilita_una_cuenta_inactiva(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    nueva = await client.post(
        f"/api/v1/condominios/{base.cid}/usuarios", headers=admin, json=datos()
    )
    uid = nueva.json()["id"]
    response = await client.put(
        f"/api/v1/condominios/{base.cid}/usuarios/{uid}/rol",
        headers=admin,
        json={"rol": "ADMIN_JUNTA"},
    )
    assert response.status_code == 200
    credentials = {"email": datos()["email"], "password": datos()["password"]}
    assert (await client.post("/api/v1/auth/login", json=credentials)).status_code == 401
    listado = (await client.get(f"/api/v1/condominios/{base.cid}/usuarios", headers=admin)).json()
    cuenta = next(usuario for usuario in listado if usuario["id"] == uid)
    assert cuenta["rol"] == "ADMIN_JUNTA" and not cuenta["esta_activo"]


async def test_junta_gestiona_roles_operativos_pero_no_otra_junta(api_usuarios):
    client, base = api_usuarios
    junta = await login(client, JUNTA, "Admin123!")
    for rol in ("AUDITOR", "RESIDENTE"):
        assert (await client.put(ruta(base), headers=junta, json={"rol": rol})).status_code == 200
    assert (
        await client.put(ruta(base), headers=junta, json={"rol": "ADMIN_JUNTA"})
    ).status_code == 403
    admin = await login(client)
    assert (
        await client.put(ruta(base), headers=admin, json={"rol": "ADMIN_JUNTA"})
    ).status_code == 200
    assert (
        await client.put(ruta(base), headers=junta, json={"rol": "RESIDENTE"})
    ).status_code == 403
    assert (await client.delete(ruta(base), headers=junta)).status_code == 403
    assert (await client.get(ruta(base), headers=junta)).json()["rol"] == "ADMIN_JUNTA"


@pytest.mark.parametrize(
    "email,password", [(JUNTA, "Admin123!"), ("superadmin@condomanager.pe", "SuperAdmin123!")]
)
async def test_autoasignacion_y_concesion_global_protegidas(api_usuarios, email, password):
    client, base = api_usuarios
    actor = await login(client, email, password)
    assert (
        await client.put(ruta(base, email), headers=actor, json={"rol": "RESIDENTE"})
    ).status_code == 403
    assert (await client.delete(ruta(base, email), headers=actor)).status_code == 403
    admin = await login(client)
    assert (
        await client.put(
            ruta(base, "superadmin@condomanager.pe"), headers=admin, json={"rol": "ADMIN_JUNTA"}
        )
    ).status_code == 403


@pytest.mark.parametrize(
    "email,password", [(RESIDENTE, "Residente123!"), ("auditor@villabonita3.pe", "Auditor123!")]
)
async def test_no_administrativos_no_gestionan_roles(api_usuarios, email, password):
    client, base = api_usuarios
    actor = await login(client, email, password)
    assert (await client.get(ruta(base), headers=actor)).status_code == 403
    assert (
        await client.put(ruta(base), headers=actor, json={"rol": "RESIDENTE"})
    ).status_code == 403
    assert (await client.delete(ruta(base), headers=actor)).status_code == 403


async def test_revocacion_logica_historial_y_restauracion(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    anterior = await login(client, RESIDENTE, "Residente123!")
    uid = id_demo(RESIDENTE)
    async with base.sessions() as db:
        original = await db.scalar(select(UsuarioRol).where(UsuarioRol.usuario_id == uid))
        asignacion_id = original.id
    revoked = await client.delete(ruta(base), headers=admin)
    assert revoked.status_code == 200 and revoked.json()["es_activo"] is False
    async with base.sessions() as db, db.begin():
        assert await cargar_demo(db) == 0
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": RESIDENTE, "password": "Residente123!"}
        )
    ).status_code == 401
    listado = (await client.get(f"/api/v1/condominios/{base.cid}/usuarios", headers=admin)).json()
    assert next(u for u in listado if u["id"] == str(uid))["rol_activo"] is False
    async with base.sessions() as db:
        assert (await db.get(Usuario, uid)).esta_activo
        assert not (await db.get(UsuarioRol, asignacion_id)).es_activo
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioDepartamento)
                .where(UsuarioDepartamento.usuario_id == uid)
            )
            == 1
        )
    assert (
        await client.put(ruta(base), headers=admin, json={"rol": "RESIDENTE"})
    ).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401
    await login(client, RESIDENTE, "Residente123!")
    async with base.sessions() as db:
        assert (await db.get(UsuarioRol, asignacion_id)).es_activo


async def test_nuevas_asignaciones_aislamiento_y_contextos(api_usuarios):
    client, base = api_usuarios
    otro = await otro_condominio(base)
    junta = await login(client, JUNTA, "Admin123!")
    admin = await login(client)
    assert (
        await client.put(ruta(base, cid=otro), headers=junta, json={"rol": "AUDITOR"})
    ).status_code == 403
    # La identidad global de SuperAdmin es la única autoridad para incorporar por UUID.
    await client.put(ruta(base, cid=otro), headers=admin, json={"rol": "AUDITOR"})
    assert (await client.get(ruta(base, cid=otro), headers=admin)).json()["rol"] == "AUDITOR"
    assert (await client.get(ruta(base), headers=admin)).json()["rol"] == "RESIDENTE"
    credentials = {"email": RESIDENTE, "password": "Residente123!"}
    choice = await client.post("/api/v1/auth/login", json=credentials)
    assert choice.status_code == 409
    segundo = await login(client, **credentials, condominio_id=str(otro))
    await client.delete(ruta(base, cid=otro), headers=admin)
    assert (await client.get("/api/v1/auth/me", headers=segundo)).status_code == 401
    unico = await client.post("/api/v1/auth/login", json=credentials)
    assert unico.status_code == 200 and unico.json()["usuario"]["condominio_id"] == base.cid
    # Junta no puede consultar ni incorporar una identidad que solo pertenece al otro contexto.
    foreign = await client.post(f"/api/v1/condominios/{otro}/usuarios", headers=admin, json=datos())
    assert foreign.status_code == 201
    no_asignado = f"/api/v1/condominios/{base.cid}/usuarios/{foreign.json()['id']}/rol"
    assert (await client.get(no_asignado, headers=junta)).status_code == 404
    assert (
        await client.put(no_asignado, headers=junta, json={"rol": "RESIDENTE"})
    ).status_code == 404


async def test_noop_auditoria_y_revision(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    await client.put(ruta(base), headers=admin, json={"rol": "RESIDENTE"})
    for _ in range(2):
        await client.put(ruta(base), headers=admin, json={"rol": "AUDITOR"})
    for _ in range(2):
        await client.delete(ruta(base), headers=admin)
    async with base.sessions() as db:
        assert (await db.get(Usuario, id_demo(RESIDENTE))).auth_revision == 3
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        assert [log.accion_ejecutada for log in logs] == ["ROL_CAMBIADO", "ROL_REVOCADO"]
        assert logs[1].hash_previo == logs[0].hash_actual
        assert logs[0].estado_anterior["rol"] == "RESIDENTE"
        assert logs[1].estado_posterior["es_activo"] is False
        assert all(log.actor_id == str(id_demo("superadmin@condomanager.pe")) for log in logs)


@pytest.mark.parametrize("nuevo_contexto", [False, True])
async def test_put_identico_concurrente_una_sola_mutacion(api_usuarios, nuevo_contexto):
    client, base = api_usuarios
    cid = await otro_condominio(base) if nuevo_contexto else base.cid
    admin = await login(client)
    responses = await asyncio.gather(
        *(client.put(ruta(base, cid=cid), headers=admin, json={"rol": "AUDITOR"}) for _ in range(2))
    )
    assert [r.status_code for r in responses] == [200, 200]
    async with base.sessions() as db:
        assert (await db.get(Usuario, id_demo(RESIDENTE))).auth_revision == 2
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM)) == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioRol)
                .where(UsuarioRol.usuario_id == id_demo(RESIDENTE), UsuarioRol.condominio_id == cid)
            )
            == 1
        )


async def test_estado_y_rol_concurrentes_sin_deadlock(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    responses = await asyncio.gather(
        client.put(ruta(base), headers=admin, json={"rol": "AUDITOR"}),
        client.patch(
            f"/api/v1/usuarios/{id_demo(RESIDENTE)}/estado?condominio_id={base.cid}",
            headers=admin,
            json={"esta_activo": False},
        ),
    )
    assert all(r.status_code == 200 for r in responses)
    async with base.sessions() as db:
        usuario = await db.get(Usuario, id_demo(RESIDENTE))
        assert not usuario.esta_activo and usuario.auth_revision == 3
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        assert len(logs) == 2 and logs[1].hash_previo == logs[0].hash_actual


async def test_fallo_auditoria_revierte_rol_revision_y_nueva_asignacion(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    otro = await otro_condominio(base)
    async with base.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE FUNCTION fallo_roles() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Fallo controlado'; END; $$"
            )
        )
        await conn.execute(
            text(
                "CREATE TRIGGER fallo_roles BEFORE INSERT ON auditoria_logs FOR EACH ROW EXECUTE FUNCTION fallo_roles()"
            )
        )
    assert (await client.put(ruta(base), headers=admin, json={"rol": "AUDITOR"})).status_code == 500
    assert (await client.delete(ruta(base), headers=admin)).status_code == 500
    assert (
        await client.put(ruta(base, cid=otro), headers=admin, json={"rol": "AUDITOR"})
    ).status_code == 500
    async with base.sessions() as db:
        assert (await db.get(Usuario, id_demo(RESIDENTE))).auth_revision == 1
        rol = await db.scalar(select(UsuarioRol).where(UsuarioRol.usuario_id == id_demo(RESIDENTE)))
        assert rol.rol == "RESIDENTE" and rol.es_activo
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioRol)
                .where(UsuarioRol.usuario_id == id_demo(RESIDENTE))
            )
            == 1
        )


async def test_revalida_actor_revocado_mientras_esperaba_bloqueo(api_usuarios, monkeypatch):
    client, base = api_usuarios
    junta = await login(client, JUNTA, "Admin123!")
    admin = await login(client)
    esperando = asyncio.Event()
    original = SQLAlchemyUsuariosRepository.por_id

    async def por_id(repo, uid, *, bloquear=False):
        if uid == id_demo(RESIDENTE) and bloquear:
            esperando.set()
        return await original(repo, uid, bloquear=bloquear)

    monkeypatch.setattr(SQLAlchemyUsuariosRepository, "por_id", por_id)
    async with base.sessions() as db:
        await db.execute(select(Usuario).where(Usuario.id == id_demo(RESIDENTE)).with_for_update())
        pendiente = asyncio.create_task(
            client.put(ruta(base), headers=junta, json={"rol": "AUDITOR"})
        )
        try:
            await asyncio.wait_for(esperando.wait(), timeout=10)
            assert (await client.delete(ruta(base, JUNTA), headers=admin)).status_code == 200
        finally:
            await db.rollback()
        assert (await asyncio.wait_for(pendiente, timeout=10)).status_code == 401
    async with base.sessions() as db:
        assert (await db.get(Usuario, id_demo(RESIDENTE))).auth_revision == 1


@pytest.mark.parametrize(
    "body",
    [
        {"rol": "SUPERADMIN"},
        {"rol": "PROPIETARIO"},
        {"rol": "INQUILINO"},
        {"rol": "COPROPIETARIO"},
        {"rol": "DESCONOCIDO"},
        {"rol": None},
        {"rol": "AUDITOR", "es_superadmin": True},
        {"rol": "AUDITOR", "es_activo": True},
    ],
)
async def test_rechaza_roles_y_campos_ajenos_al_contrato(api_usuarios, body):
    client, base = api_usuarios
    admin = await login(client)
    result = await client.put(ruta(base), headers=admin, json=body)
    assert result.status_code == 422 and result.json()["error_code"] == "DATOS_ROL_INVALIDOS"


async def test_recursos_inexistentes_validacion_uuid_y_sin_token(api_usuarios):
    client, base = api_usuarios
    assert (await client.get(ruta(base))).status_code == 401
    admin = await login(client)
    inexistente = f"/api/v1/condominios/{base.cid}/usuarios/{uuid4()}/rol"
    assert (await client.get(inexistente, headers=admin)).status_code == 404
    assert (
        await client.put(inexistente, headers=admin, json={"rol": "AUDITOR"})
    ).status_code == 404
    assert (await client.delete(inexistente, headers=admin)).status_code == 404
    assert (await client.get(ruta(base, cid=uuid4()), headers=admin)).status_code == 404
    invalid = await client.put(
        f"/api/v1/condominios/{base.cid}/usuarios/invalido/rol",
        headers=admin,
        json={"rol": "AUDITOR"},
    )
    assert invalid.status_code == 422 and invalid.json()["error_code"] == "DATOS_ROL_INVALIDOS"


async def test_migracion_conserva_asignaciones_y_downgrade_no_rehabilita_revocaciones(db_usuarios):
    base = db_usuarios
    revision = import_module("migrations.versions.20261020_0008_roles_revocables")

    def ejecutar(conn, operacion):
        with Operations.context(MigrationContext.configure(conn)):
            operacion()

    async with base.engine.begin() as conn:
        await conn.run_sync(lambda c: ejecutar(c, revision.downgrade))
        assert await conn.scalar(text("SELECT count(*) FROM usuario_roles")) == 5
        await conn.run_sync(lambda c: ejecutar(c, revision.upgrade))
        assert await conn.scalar(text("SELECT count(*) FROM usuario_roles WHERE es_activo")) == 5
        await conn.execute(
            text("UPDATE usuario_roles SET es_activo=false WHERE usuario_id=:uid"),
            {"uid": id_demo(RESIDENTE)},
        )
    with pytest.raises(RuntimeError, match="revocados"):
        async with base.engine.begin() as conn:
            await conn.run_sync(lambda c: ejecutar(c, revision.downgrade))
    async with base.engine.connect() as conn:
        assert "es_activo" in await conn.run_sync(
            lambda c: {x["name"] for x in inspect(c).get_columns("usuario_roles")}
        )
        assert (
            await conn.scalar(text("SELECT count(*) FROM usuario_roles WHERE NOT es_activo")) == 1
        )
