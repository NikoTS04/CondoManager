"""CON-04: identidad real, aislamiento, revocación, rollback y concurrencia SQL."""

import asyncio
from importlib import import_module
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text

from scripts.seed_usuarios_demo import cargar_demo
from src.core.models_audit import AuditoriaLogORM
from src.core.security import create_access_token, decode_access_token, verify_password
from src.modules.condominios.models import Condominio
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
PASSWORD = "Inicial123!"


def datos(**overrides):
    return {
        "email": "nuevo@ejemplo.test",
        "password": PASSWORD,
        "nombre": "Ana",
        "apellido": "Pérez",
        "documento_identidad": "ABC12345",
        **overrides,
    }


async def login(client, email="superadmin@condomanager.pe", password="SuperAdmin123!", **extra):
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password, **extra}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


async def crear(client, base, headers, **overrides):
    return await client.post(
        f"/api/v1/condominios/{base.cid}/usuarios", headers=headers, json=datos(**overrides)
    )


async def estado(client, base, headers, uid, activo=True):
    return await client.patch(
        f"/api/v1/usuarios/{uid}/estado",
        params={"condominio_id": base.cid},
        headers=headers,
        json={"esta_activo": activo},
    )


async def test_alta_inactiva_hash_habilitacion_y_persistencia(api_usuarios):
    client, base = api_usuarios
    superadmin = await login(client)
    response = await crear(
        client, base, superadmin, email=" NUEVO@ejemplo.test ", documento_identidad=" abc12345 "
    )
    assert response.status_code == 201, response.text
    cuenta = response.json()
    assert cuenta["esta_activo"] is False and cuenta["email"] == "nuevo@ejemplo.test"
    assert cuenta["documento_identidad"] == "ABC12345"
    assert "password" not in response.text and "auth_revision" not in response.text
    async with base.sessions() as db:
        usuario = await db.get(Usuario, UUID(cuenta["id"]))
        assert (
            verify_password(PASSWORD, usuario.password_hash) and usuario.password_hash != PASSWORD
        )
        assert usuario.auth_revision == 1 and not usuario.es_superadmin
        assert (
            await db.scalar(select(UsuarioRol).where(UsuarioRol.usuario_id == usuario.id))
        ).rol == "RESIDENTE"
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioDepartamento)
                .where(UsuarioDepartamento.usuario_id == usuario.id)
            )
            == 0
        )
    body = {"email": cuenta["email"], "password": PASSWORD}
    assert (await client.post("/api/v1/auth/login", json=body)).status_code == 401
    assert (await estado(client, base, superadmin, cuenta["id"])).status_code == 200
    headers = await login(client, cuenta["email"], PASSWORD)
    await base.engine.dispose()  # nuevas conexiones; no identidad en memoria
    perfil = await client.get("/api/v1/auth/me", headers=headers)
    assert perfil.status_code == 200
    assert perfil.json()["id"] == cuenta["id"] and perfil.json()["departamentos"] == []
    assert (
        await client.get(f"/api/v1/condominios/{base.cid}/usuarios", headers=headers)
    ).status_code == 403


async def test_solo_superadmin_estado_y_validaciones_sin_secretos(api_usuarios):
    client, base = api_usuarios
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    response = await crear(client, base, junta)
    assert response.status_code == 201
    uid = response.json()["id"]
    assert (await estado(client, base, junta, uid)).status_code == 403
    for campo, valor in (
        ("esta_activo", True),
        ("es_superadmin", True),
        ("rol", "SUPERADMIN"),
        ("auth_revision", 9),
    ):
        invalid = await crear(client, base, junta, **{campo: valor})
        assert invalid.status_code == 422 and PASSWORD not in invalid.text
    for password in ("corta", "x" * 129):
        invalid = await crear(client, base, junta, password=password)
        assert invalid.status_code == 422 and password not in invalid.text
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (await crear(client, base, auditor)).status_code == 403
    payload = decode_access_token(junta["Authorization"].split()[1])
    payload["rol"] = "SUPERADMIN"
    forged = {"Authorization": "Bearer " + create_access_token(payload)}
    assert (await estado(client, base, forged, uid)).status_code == 401


async def test_revocacion_en_todas_las_guardias_y_reactivacion(api_usuarios):
    client, base = api_usuarios
    superadmin = await login(client)
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    uid = str(id_demo("admin@villabonita3.pe"))
    assert (await estado(client, base, superadmin, uid, False)).status_code == 200
    rutas = [
        "/auth/me",
        "/condominios",
        f"/condominios/{base.cid}/usuarios",
        f"/condominios/{base.cid}/edificios",
        f"/condominios/{base.cid}/distribucion",
        f"/condominios/{base.cid}/presupuestos/2026-10",
        "/areas",
        "/reservas",
        "/pagos/comprobantes",
        "/notificaciones/logs",
        "/cuotas/departamentos",
    ]
    for ruta in rutas:
        result = await client.get("/api/v1" + ruta, headers=junta)
        assert result.status_code == 401, (ruta, result.text)
    assert (await estado(client, base, superadmin, uid, True)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=junta)).status_code == 401
    renovada = await login(client, "admin@villabonita3.pe", "Admin123!")
    assert (await client.get("/api/v1/auth/me", headers=renovada)).status_code == 200


async def test_noop_y_auditoria_encadenada(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    response = await crear(client, base, headers)
    uid = response.json()["id"]
    await estado(client, base, headers, uid)
    await estado(client, base, headers, uid)
    async with base.sessions() as db:
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        assert [log.accion_ejecutada for log in logs] == ["ALTA_USUARIO", "USUARIO_ESTADO_CAMBIADO"]
        assert logs[1].hash_previo == logs[0].hash_actual
        assert all(log.actor_id == str(id_demo("superadmin@condomanager.pe")) for log in logs)
        assert (await db.get(Usuario, UUID(uid))).auth_revision == 2


async def otro_condominio(base):
    cid = uuid4()
    async with base.sessions() as db, db.begin():
        db.add(
            Condominio(
                id=cid,
                nombre="Otro",
                direccion="Prueba",
                moneda="PEN",
                regla_mora_tipo="MONTO_FIJO",
                monto_mora_fijo=0,
                dia_vencimiento=20,
                dias_gracia=0,
            )
        )
    return cid


async def test_aislamiento_y_seleccion_de_asignaciones(api_usuarios):
    client, base = api_usuarios
    otro = await otro_condominio(base)
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    ruta = f"/api/v1/condominios/{otro}/usuarios"
    assert (await client.get(ruta, headers=junta)).status_code == 403
    assert (await client.post(ruta, headers=junta, json=datos())).status_code == 403
    uid = id_demo("residente102@villabonita3.pe")
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=uid, condominio_id=otro, rol="RESIDENTE"))
    credentials = {"email": "residente102@villabonita3.pe", "password": "Residente123!"}
    choice = await client.post("/api/v1/auth/login", json=credentials)
    assert choice.status_code == 409
    assert {c["id"] for c in choice.json()["detalles"]["condominios"]} == {base.cid, str(otro)}
    headers = await login(client, **credentials, condominio_id=str(otro))
    perfil = await client.get("/api/v1/auth/me", headers=headers)
    assert perfil.json()["condominio_id"] == str(otro) and perfil.json()["departamentos"] == []
    superadmin = await login(client)
    wrong = await client.patch(
        f"/api/v1/usuarios/{id_demo('admin@villabonita3.pe')}/estado",
        headers=superadmin,
        params={"condominio_id": str(otro)},
        json={"esta_activo": False},
    )
    assert wrong.status_code == 404


async def test_unicidad_concurrente_entre_condominios(api_usuarios):
    client, base = api_usuarios
    otro = await otro_condominio(base)
    headers = await login(client)
    requests = [
        client.post(
            f"/api/v1/condominios/{cid}/usuarios",
            headers=headers,
            json=datos(email=" NUEVO@EJEMPLO.TEST " if index else "nuevo@ejemplo.test"),
        )
        for index, cid in enumerate((base.cid, otro))
    ]
    responses = await asyncio.gather(*requests)
    assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
    document_duplicate = await crear(
        client, base, headers, email="diferente@ejemplo.test", documento_identidad=" abc12345 "
    )
    assert document_duplicate.status_code == 409
    async with base.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Usuario)
                .where(Usuario.email == "nuevo@ejemplo.test")
            )
            == 1
        )


async def test_fallo_auditoria_revierte_alta_y_cambio_de_estado(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    async with base.engine.begin() as conn:
        await conn.execute(
            text("""CREATE FUNCTION rechazar_auditoria() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'Fallo de auditoria controlado'; END; $$""")
        )
        await conn.execute(
            text(
                "CREATE TRIGGER fallo_auditoria BEFORE INSERT ON auditoria_logs FOR EACH ROW EXECUTE FUNCTION rechazar_auditoria()"
            )
        )
    response = await crear(client, base, headers)
    assert response.status_code == 500
    uid = id_demo("admin@villabonita3.pe")
    assert (await estado(client, base, headers, str(uid), False)).status_code == 500
    async with base.sessions() as db:
        assert (
            await db.scalar(select(Usuario.id).where(Usuario.email == "nuevo@ejemplo.test")) is None
        )
        usuario = await db.get(Usuario, uid)
        assert usuario.esta_activo and usuario.auth_revision == 1


async def test_seed_conserva_estado_y_hash_y_no_otorga_superadmin_contextual(api_usuarios):
    client, base = api_usuarios
    uid = id_demo("admin@villabonita3.pe")
    async with base.sessions() as db, db.begin():
        usuario = await db.get(Usuario, uid)
        original = usuario.password_hash
        usuario.esta_activo = False
    async with base.sessions() as db, db.begin():
        assert await cargar_demo(db) == 0
        usuario = await db.get(Usuario, uid)
        assert not usuario.esta_activo and usuario.password_hash == original
        usuario.esta_activo = True
        rol = await db.scalar(select(UsuarioRol).where(UsuarioRol.usuario_id == uid))
        rol.rol = "SUPERADMIN"
    rejected = await client.post(
        "/api/v1/auth/login", json={"email": "admin@villabonita3.pe", "password": "Admin123!"}
    )
    assert rejected.status_code == 401


async def test_migracion_adopta_conserva_estados_y_downgrade(db_usuarios):
    base = db_usuarios
    # Las tablas con datos se convierten en preexistentes para ejercitar adopción.
    revision = import_module("migrations.versions.20261020_0007_alta_usuarios")
    async with base.engine.begin() as conn:
        for tabla in ("usuarios", "usuario_roles", "usuario_departamentos"):
            await conn.execute(text(f"COMMENT ON TABLE {tabla} IS 'Tabla preexistente'"))
        await conn.run_sync(lambda c: _operacion(c, revision.downgrade))
        await conn.run_sync(lambda c: _operacion(c, revision.upgrade))
        columnas = await conn.run_sync(
            lambda c: {x["name"] for x in inspect(c).get_columns("usuarios")}
        )
        assert {"es_superadmin", "auth_revision"} <= columnas
        assert await conn.scalar(text("SELECT count(*) FROM usuarios WHERE esta_activo")) == 6
        assert await conn.scalar(text("SELECT count(*) FROM usuarios WHERE es_superadmin")) == 0
        nuevo = uuid4()
        await conn.execute(
            text("""INSERT INTO usuarios (id,email,password_hash,nombre,apellido,documento_identidad)
            VALUES (:id,'default@ejemplo.test','hash','Prueba','Default','DEFAULT001')"""),
            {"id": nuevo},
        )
        assert (
            await conn.scalar(text("SELECT esta_activo FROM usuarios WHERE id=:id"), {"id": nuevo})
            is False
        )


def _operacion(connection, operation):
    with Operations.context(MigrationContext.configure(connection)):
        operation()
