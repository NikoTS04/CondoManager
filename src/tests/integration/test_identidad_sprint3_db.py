"""CON-76/7: enlaces secretos, transacciones, concurrencia y avisos SQL reales."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select, text

from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.core.security import decode_access_token, verify_password
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.modules.usuarios.comunicaciones import contenido_entrega
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.invitaciones_models import InvitacionUsuario
from src.modules.usuarios.models import Usuario, UsuarioDepartamento
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
PASSWORD = "ElegidaPorInvitado123!"


@pytest.fixture(autouse=True)
def configuracion_identidad(monkeypatch):
    monkeypatch.setattr(settings, "IDENTITY_DELIVERY_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ACTIVACION_WEB_URL", "https://condo.ejemplo.test/activar")


def datos(**extra):
    return {
        "email": "invitado@ejemplo.test",
        "nombre": "Ana",
        "apellido": "Invitada",
        "documento_identidad": "INVITADO001",
        **extra,
    }


def ruta(base):
    return f"/api/v1/condominios/{base.cid}/invitaciones"


def clave(headers, key=None):
    return {**headers, "Idempotency-Key": str(key or uuid4())}


async def invitar(client, base, headers=None, key=None, **extra):
    headers = headers or await login(client)
    response = await client.post(ruta(base), headers=clave(headers, key), json=datos(**extra))
    assert response.status_code == 201, response.text
    return response.json()


async def token_invitacion(base, iid):
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion).where(Notificacion.operacion_id == UUID(iid)))
        enlace = next(
            linea for linea in contenido_entrega(log).splitlines() if linea.startswith("https://")
        )
        return parse_qs(urlsplit(enlace).fragment)["token"][0]


async def activar(client, token):
    return await client.post("/api/v1/auth/activar", json={"token": token, "password": PASSWORD})


async def test_invitacion_hash_activacion_y_cuentas_previas(api_usuarios):
    client, base = api_usuarios
    async with base.sessions() as db:
        originales = {
            u.id: (u.password_hash, u.esta_activo) for u in await db.scalars(select(Usuario))
        }
    cuenta = await invitar(client, base, email=" INVITADO@EJEMPLO.TEST ")
    token = await token_invitacion(base, cuenta["id"])
    async with base.sessions() as db:
        i = await db.get(InvitacionUsuario, UUID(cuenta["id"]))
        assert token not in i.token_hash and len(i.token_hash) == 64
        logs = list(await db.scalars(select(Notificacion)))
        assert len(logs) == 1 and logs[0].departamento_id is None
        assert token not in logs[0].cuerpo and token not in logs[0].contenido_cifrado
        assert logs[0].transporte == "PROVEEDOR"
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": cuenta["email"], "password": PASSWORD}
        )
    ).status_code == 401
    assert (await activar(client, token)).status_code == 200
    assert (await activar(client, token)).json()["error_code"] == "ACTIVACION_USADA"
    await base.engine.dispose()
    headers = await login(client, cuenta["email"], PASSWORD)
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()["rol"] == "RESIDENTE"
    async with base.sessions() as db:
        for uid, original in originales.items():
            usuario = await db.get(Usuario, uid)
            assert (usuario.password_hash, usuario.esta_activo) == original
        usuario = await db.get(Usuario, UUID(cuenta["usuario_id"]))
        assert verify_password(PASSWORD, usuario.password_hash) and not usuario.activacion_pendiente


async def test_activacion_concurrente_una_sola_gana(api_usuarios):
    client, base = api_usuarios
    cuenta = await invitar(client, base)
    token = await token_invitacion(base, cuenta["id"])
    respuestas = await asyncio.gather(activar(client, token), activar(client, token))
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    async with base.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "USUARIO_ACTIVADO")
            )
            == 1
        )


async def test_reintento_creacion_y_conflicto_idempotencia(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    key = uuid4()
    respuestas = await asyncio.gather(
        *[client.post(ruta(base), headers=clave(headers, key), json=datos()) for _ in range(2)]
    )
    assert all(r.status_code == 201 for r in respuestas)
    assert respuestas[0].json() == respuestas[1].json()
    r = await client.post(ruta(base), headers=clave(headers, key), json=datos(nombre="Otro"))
    assert r.status_code == 409 and r.json()["error_code"] == "IDEMPOTENCIA_CONFLICTO"
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(InvitacionUsuario)) == 1
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1


async def test_reenvio_revoca_anterior_y_reintento_no_duplica(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    cuenta = await invitar(client, base, headers)
    viejo = await token_invitacion(base, cuenta["id"])
    url = f"{ruta(base)}/{cuenta['id']}/reenviar"
    key = uuid4()
    respuestas = await asyncio.gather(
        *[client.post(url, headers=clave(headers, key)) for _ in range(2)]
    )
    assert all(r.status_code == 200 for r in respuestas), [r.text for r in respuestas]
    assert respuestas[0].json() == respuestas[1].json()
    nuevo = respuestas[0].json()
    assert (await activar(client, viejo)).json()["error_code"] == "ACTIVACION_REVOCADA"
    assert (await activar(client, await token_invitacion(base, nuevo["id"]))).status_code == 200


@pytest.mark.parametrize("caso", ["expirada", "revocada", "rol_revocado", "deshabilitada"])
async def test_enlaces_no_autorizados_no_activan(api_usuarios, caso):
    client, base = api_usuarios
    headers = await login(client)
    cuenta = await invitar(client, base, headers)
    token = await token_invitacion(base, cuenta["id"])
    if caso == "expirada":
        async with base.sessions() as db, db.begin():
            i = await db.get(InvitacionUsuario, UUID(cuenta["id"]))
            i.creado_en = datetime.now(UTC) - timedelta(days=2)
            i.expira_en = datetime.now(UTC) - timedelta(days=1)
    elif caso == "revocada":
        assert (
            await client.delete(f"{ruta(base)}/{cuenta['id']}", headers=clave(headers))
        ).status_code == 200
    elif caso == "rol_revocado":
        assert (
            await client.delete(
                f"/api/v1/condominios/{base.cid}/usuarios/{cuenta['usuario_id']}/rol",
                headers=headers,
            )
        ).status_code == 200
    else:
        response = await client.patch(
            f"/api/v1/usuarios/{cuenta['usuario_id']}/estado?condominio_id={base.cid}",
            headers=headers,
            json={"esta_activo": False},
        )
        assert response.status_code == 200
    response = await activar(client, token)
    assert response.status_code == 400, response.text
    async with base.sessions() as db:
        assert not (await db.get(Usuario, UUID(cuenta["usuario_id"]))).esta_activo


async def test_permisos_contexto_y_no_elevacion(api_usuarios):
    client, base = api_usuarios
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    otro = await otro_condominio(base)
    for email, password in (
        ("auditor@villabonita3.pe", "Auditor123!"),
        ("residente102@villabonita3.pe", "Residente123!"),
    ):
        headers = await login(client, email, password)
        assert (
            await client.post(ruta(base), headers=clave(headers), json=datos())
        ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/condominios/{otro}/invitaciones", headers=clave(junta), json=datos()
        )
    ).status_code == 403
    assert (
        await client.post(ruta(base), headers=clave(junta), json=datos(rol="ADMIN_JUNTA"))
    ).status_code == 422
    cuenta = await invitar(client, base, junta)
    root = await login(client)
    assert (
        await client.patch(
            f"/api/v1/usuarios/{cuenta['usuario_id']}/estado?condominio_id={base.cid}",
            headers=root,
            json={"esta_activo": True},
        )
    ).status_code == 409
    assert (
        await client.post(
            "/api/v1/auth/activar",
            json={"token": "x" * 43, "password": PASSWORD, "es_superadmin": True},
        )
    ).status_code == 422


async def fallo_auditoria(base):
    async with base.engine.begin() as conn:
        await conn.execute(
            text("""CREATE FUNCTION fallo_identidad() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'Fallo controlado'; END; $$""")
        )
        await conn.execute(
            text(
                "CREATE TRIGGER fallo_identidad BEFORE INSERT ON auditoria_logs FOR EACH ROW EXECUTE FUNCTION fallo_identidad()"
            )
        )


async def test_rollback_alta_y_activacion(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    cuenta = await invitar(client, base, headers)
    token = await token_invitacion(base, cuenta["id"])
    await fallo_auditoria(base)
    assert (
        await client.post(
            ruta(base),
            headers=clave(headers),
            json=datos(email="otra@test.test", documento_identidad="OTRAINV001"),
        )
    ).status_code == 500
    assert (await activar(client, token)).status_code == 500
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(InvitacionUsuario)) == 1
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1
        assert not (await db.get(Usuario, UUID(cuenta["usuario_id"]))).esta_activo
        assert (await db.get(InvitacionUsuario, UUID(cuenta["id"]))).utilizada_en is None


async def test_cola_no_simula_identidad_y_proveedor_inyectado_recupera(api_usuarios):
    client, base = api_usuarios
    cuenta = await invitar(client, base)
    assert await procesar_uno(base.sessions)
    async with base.sessions() as db, db.begin():
        log = await db.get(Notificacion, UUID(cuenta["notificacion_id"]))
        assert (
            log.estado == "FALLIDO_PERMANENTE" and log.error_mensaje == "PROVEEDOR_NO_CONFIGURADO"
        )
    headers = await login(client)
    r = await client.post(
        f"/api/v1/notificaciones/reenviar/{cuenta['notificacion_id']}", headers=headers, json={}
    )
    assert r.status_code == 200, r.text
    recibidos = []

    def transporte(log, key):
        recibidos.append(log.cuerpo)
        return {"status": 200, "message_id": "proveedor-prueba"}

    assert await procesar_uno(base.sessions, transport=transporte)
    assert len(recibidos) == 1 and "#token=" in recibidos[0]
    async with base.sessions() as db:
        log = await db.get(Notificacion, UUID(cuenta["notificacion_id"]))
        assert log.estado == "ENVIADO" and "#token=" not in log.cuerpo
    assert not await procesar_uno(base.sessions, transport=transporte)


async def preparar_relevo(client, base):
    headers = await login(client)
    saliente = id_demo("inquilino504@villabonita3.pe")
    entrante = id_demo("residente102@villabonita3.pe")
    async with base.sessions() as db:
        vinculo = await db.scalar(
            select(UsuarioDepartamento).where(UsuarioDepartamento.usuario_id == saliente)
        )
        did, vid = vinculo.departamento_id, vinculo.id
    async with base.sessions() as db, db.begin():
        db.add(
            UsuarioDepartamento(
                usuario_id=id_demo("moroso402@villabonita3.pe"),
                departamento_id=did,
                tipo_relacion="PROPIETARIO_TITULAR",
                es_activo=True,
            )
        )
    # Designación real que el relevo debe limpiar sin tocar cuotas históricas.
    r = await client.get(f"/api/v1/departamentos/{did}/condiciones-pago", headers=headers)
    r = await client.put(
        f"/api/v1/departamentos/{did}/condiciones-pago",
        headers=headers,
        json={
            "version_esperada": r.json()["version"],
            "vinculo_responsable_id": str(vid),
            "dias_gracia_override": 3,
            "motivo": "Preparar relevo de prueba",
        },
    )
    assert r.status_code == 200, r.text
    body = {
        "tipo": "INQUILINO",
        "saliente_id": str(saliente),
        "entrante_id": str(entrante),
        "departamento_id": str(did),
    }
    return headers, body


async def test_relevo_inquilino_atomico_idempotente_y_avisa_al_revocado(api_usuarios):
    client, base = api_usuarios
    headers, body = await preparar_relevo(client, base)
    anterior = await login(client, "inquilino504@villabonita3.pe", "Inquilino123!")
    key = uuid4()
    url = f"/api/v1/condominios/{base.cid}/relevos"
    r = await client.post(url, headers=clave(headers, key), json=body)
    assert r.status_code == 200, r.text
    assert (await client.post(url, headers=clave(headers, key), json=body)).json() == r.json()
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401
    renovada = await login(client, "inquilino504@villabonita3.pe", "Inquilino123!")
    unidades = (await client.get("/api/v1/cuotas/departamentos", headers=renovada)).json()
    assert body["departamento_id"] not in {unidad["id"] for unidad in unidades}
    # La pertenencia SQL queda revocada; /auth/me la conserva solo como historial inactivo.
    perfil = (await client.get("/api/v1/auth/me", headers=renovada)).json()
    assert not any(
        v["es_activo"]
        for v in perfil["departamentos"]
        if v["departamento_id"] == body["departamento_id"]
    )
    condiciones = (
        await client.get(
            f"/api/v1/departamentos/{body['departamento_id']}/condiciones-pago", headers=headers
        )
    ).json()
    assert condiciones["vinculo_responsable_id"] is None
    recibidos = []

    def proveedor(log, key):
        recibidos.append(log.usuario_destinatario_id)
        return {"status": 200, "message_id": key}

    while await procesar_uno(base.sessions, transport=proveedor):
        pass
    assert UUID(body["saliente_id"]) in recibidos and UUID(body["entrante_id"]) in recibidos
    async with base.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Notificacion)
                .where(Notificacion.tipo_evento == "AccesoUsuarioCambiadoEvent")
            )
            == 2
        )


async def test_relevo_rollback_y_junta_solo_superadmin(api_usuarios):
    client, base = api_usuarios
    headers, body = await preparar_relevo(client, base)
    await fallo_auditoria(base)
    r = await client.post(
        f"/api/v1/condominios/{base.cid}/relevos", headers=clave(headers), json=body
    )
    assert r.status_code == 500
    async with base.sessions() as db:
        vinculos = list(
            await db.scalars(
                select(UsuarioDepartamento).where(
                    UsuarioDepartamento.departamento_id == UUID(body["departamento_id"])
                )
            )
        )
        assert any(v.usuario_id == UUID(body["saliente_id"]) and v.es_activo for v in vinculos)
        assert not any(v.usuario_id == UUID(body["entrante_id"]) and v.es_activo for v in vinculos)
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 0


async def test_relevo_junta_conserva_cuenta_y_vinculos(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    saliente = id_demo("admin@villabonita3.pe")
    entrante = id_demo("residente102@villabonita3.pe")
    body = {
        "tipo": "JUNTA",
        "saliente_id": str(saliente),
        "entrante_id": str(entrante),
        "rol_saliente": "AUDITOR",
    }
    url = f"/api/v1/condominios/{base.cid}/relevos"
    assert (await client.post(url, headers=clave(junta), json=body)).status_code == 403
    r = await client.post(url, headers=clave(headers), json=body)
    assert r.status_code == 200, r.text
    assert (await client.get("/api/v1/auth/me", headers=junta)).status_code == 401
    nueva = await login(client, "admin@villabonita3.pe", "Admin123!")
    assert (await client.get("/api/v1/auth/me", headers=nueva)).json()["rol"] == "AUDITOR"
    async with base.sessions() as db:
        assert (await db.get(Usuario, saliente)).esta_activo
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioDepartamento)
                .where(UsuarioDepartamento.usuario_id == entrante, UsuarioDepartamento.es_activo)
            )
            == 1
        )


async def test_duracion_configurable_y_log_sin_secretos(api_usuarios, monkeypatch, caplog):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 7)
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "residente102@villabonita3.pe", "password": "Residente123!"},
    )
    body = r.json()
    claims = decode_access_token(body["access_token"])
    assert body["expires_in"] == claims["exp"] - claims["iat"] == 420
    with caplog.at_level("INFO", logger="condomanager.seguridad"):
        r = await client.get(
            ruta(base), headers={"Authorization": "Bearer " + body["access_token"]}
        )
    assert r.status_code == 403
    registro = json.loads(
        next(record.message for record in caplog.records if record.name == "condomanager.seguridad")
    )
    assert registro["actor_id"] == claims["sub"]
    assert registro["contexto"]["condominio_id"] == base.cid
    assert registro["correlacion"] == r.headers["X-Correlation-ID"]
    assert body["access_token"] not in caplog.text and "Residente123!" not in caplog.text


async def test_sin_clave_de_entrega_no_deja_identidad_huerfana(api_usuarios, monkeypatch):
    client, base = api_usuarios
    headers = await login(client)
    monkeypatch.setattr(settings, "IDENTITY_DELIVERY_KEY", "")
    response = await client.post(ruta(base), headers=clave(headers), json=datos())
    assert response.status_code == 503
    async with base.sessions() as db:
        assert await db.scalar(select(Usuario.id).where(Usuario.email == datos()["email"])) is None
        assert await db.scalar(select(func.count()).select_from(InvitacionUsuario)) == 0
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 0


async def test_historial_no_expone_secreto_y_revalida_antes_del_despacho(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    cuenta = await invitar(client, base, headers)
    token = await token_invitacion(base, cuenta["id"])
    for url in (ruta(base), f"/api/v1/notificaciones/logs?condominio_id={base.cid}"):
        response = await client.get(url, headers=headers)
        assert response.status_code == 200
        assert token not in response.text and "contenido_cifrado" not in response.text
        assert "token_hash" not in response.text
    assert (await activar(client, token)).status_code == 200

    def transporte_prohibido(*args):
        pytest.fail("La invitación consumida no se envía")

    assert await procesar_uno(base.sessions, transport=transporte_prohibido)
    alertas = await client.get(
        f"/api/v1/notificaciones/alertas?condominio_id={base.cid}", headers=headers
    )
    assert alertas.status_code == 200
    assert alertas.json()[0]["departamento_id"] is None
    assert alertas.json()[0]["tipo"] == "DESTINATARIO_INVALIDO"


async def test_cambio_previo_de_permisos_requiere_nuevo_enlace(api_usuarios):
    client, base = api_usuarios
    headers = await login(client)
    cuenta = await invitar(client, base, headers)
    viejo = await token_invitacion(base, cuenta["id"])
    response = await client.put(
        f"/api/v1/condominios/{base.cid}/usuarios/{cuenta['usuario_id']}/rol",
        headers=headers,
        json={"rol": "AUDITOR"},
    )
    assert response.status_code == 200
    assert (await activar(client, viejo)).json()["error_code"] == "ACTIVACION_NO_AUTORIZADA"
    response = await client.post(f"{ruta(base)}/{cuenta['id']}/reenviar", headers=clave(headers))
    assert response.status_code == 200
    assert (
        await activar(client, await token_invitacion(base, response.json()["id"]))
    ).status_code == 200
    auditor = await login(client, cuenta["email"], PASSWORD)
    assert (await client.get("/api/v1/auth/me", headers=auditor)).json()["rol"] == "AUDITOR"


async def test_relevo_conserva_historia_financiera_y_reservas(api_usuarios, monkeypatch, tmp_path):
    from datetime import date
    from decimal import Decimal

    from src.modules.cuotas.models import CuotaMantenimiento
    from src.tests.integration.test_catalogo_areas_db import turno
    from src.tests.integration.test_pagos_db import reportar

    client, base = api_usuarios
    headers, body = await preparar_relevo(client, base)
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path))
    saliente = await login(client, "inquilino504@villabonita3.pe", "Inquilino123!")
    response = await client.post(
        "/api/v1/reservas",
        headers=saliente,
        json=turno(base, "11111111-1111-1111-1111-111111111101", did=body["departamento_id"]),
    )
    assert response.status_code == 201, response.text
    pago = await reportar(client, saliente, numero="504", monto="20.00")
    assert pago.status_code == 202, pago.text
    async with base.sessions() as db, db.begin():
        db.add(
            CuotaMantenimiento(
                id=uuid4(),
                departamento_id=UUID(body["departamento_id"]),
                periodo="2026-09",
                monto_ordinario=Decimal("20.00"),
                monto_total_exigible=Decimal("20.00"),
                monto_pagado=Decimal("20.00"),
                estado="PAGADA",
                fecha_emision=date(2026, 9, 1),
                fecha_vencimiento=date(2026, 9, 20),
                dias_gracia_aplicados=3,
                politica_mora_aplicada={"regla_mora_tipo": "MONTO_FIJO", "dias_gracia": 3},
            )
        )

    async def historia():
        async with base.sessions() as db:
            return {
                tabla: {
                    str(fila["id"]): fila
                    for fila in await db.scalars(text(f"SELECT to_jsonb(t) FROM {tabla} t"))
                }
                for tabla in (
                    "cuotas_mantenimiento",
                    "comprobantes_pago",
                    "reservas",
                    "auditoria_logs",
                )
            }

    anterior = await historia()
    response = await client.post(
        f"/api/v1/condominios/{base.cid}/relevos", headers=clave(headers), json=body
    )
    assert response.status_code == 200, response.text
    await base.engine.dispose()
    posterior = await historia()
    for tabla, filas in anterior.items():
        assert filas and all(posterior[tabla].get(id) == fila for id, fila in filas.items())
    recibos = await client.get(
        f"/api/v1/pagos/comprobantes?condominio_id={base.cid}", headers=headers
    )
    assert pago.json()["comprobante_id"] in {p["id"] for p in recibos.json()}


async def test_migracion_conserva_cuentas_y_protege_historia_de_identidad(api_usuarios):
    from importlib import import_module

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import DBAPIError

    client, base = api_usuarios
    revision = import_module("migrations.versions.20261113_0021_invitaciones_identidad")

    def aplicar(connection, operacion):
        with Operations.context(MigrationContext.configure(connection)):
            operacion()

    async with base.engine.begin() as conn:
        await conn.run_sync(aplicar, revision.downgrade)
        consulta = text(
            "SELECT id,password_hash,esta_activo,es_superadmin FROM usuarios ORDER BY id"
        )
        antes = (await conn.execute(consulta)).all()
        await conn.run_sync(aplicar, revision.upgrade)
        assert (await conn.execute(consulta)).all() == antes
        assert (
            await conn.scalar(text("SELECT count(*) FROM usuarios WHERE activacion_pendiente")) == 0
        )
    cuenta = await invitar(client, base)
    async with base.engine.begin() as conn:
        with pytest.raises(DBAPIError, match="historial"):
            async with conn.begin_nested():
                await conn.run_sync(aplicar, revision.downgrade)
        assert await conn.scalar(text("SELECT count(*) FROM invitaciones_usuario")) == 1
    assert (await activar(client, await token_invitacion(base, cuenta["id"]))).status_code == 200
