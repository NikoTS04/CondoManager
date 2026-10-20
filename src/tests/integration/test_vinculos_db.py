"""CON-05: unidades reales, tenencia, titulares y autorización en PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text

from src.core.models_audit import AuditoriaLogORM
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.pagos import router as pagos
from src.modules.reservas import router as reservas
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository
from src.tests.integration.test_alta_usuarios_db import datos, login, otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
TITULAR = "PROPIETARIO_TITULAR"
A = "residente102@villabonita3.pe"
B = "inquilino504@villabonita3.pe"


async def estructura(client, cid, headers, nombre="Bloque CON-05"):
    edificio = await client.post(
        f"/api/v1/condominios/{cid}/edificios",
        headers=headers,
        json={"nombre_bloque": nombre, "total_pisos": 2},
    )
    assert edificio.status_code == 201, edificio.text
    unidades = []
    for numero in ("NUEVA-1", "NUEVA-2"):
        unidad = await client.post(
            f"/api/v1/condominios/{cid}/edificios/{edificio.json()['id']}/departamentos",
            headers=headers,
            json={"numero": numero, "piso": 1, "coeficiente_participacion": "1.0000"},
        )
        assert unidad.status_code == 201, unidad.text
        unidades.append(unidad.json()["id"])
    return unidades


@pytest_asyncio.fixture
async def caso(api_usuarios, monkeypatch):
    client, base = api_usuarios
    monkeypatch.setattr(pagos, "COMPROBANTES_REGISTRADOS", {})
    monkeypatch.setattr(reservas, "RESERVAS_REGISTRADAS", {})
    admin = await login(client)
    unidades = await estructura(client, base.cid, admin)
    return {"client": client, "base": base, "admin": admin, "unidades": unidades}


def ruta(caso, email=A, unidad=0, *, cid=None, uid=None):
    return (
        f"/api/v1/condominios/{cid or caso['base'].cid}/usuarios/{uid or id_demo(email)}/departamentos"
        + ("" if unidad is None else "/" + caso["unidades"][unidad])
    )


async def vincular(caso, email=A, unidad=0, relacion=TITULAR, actor=None):
    return await caso["client"].put(
        ruta(caso, email, unidad), headers=actor or caso["admin"], json={"tipo_relacion": relacion}
    )


async def logs_vinculos(base):
    async with base.sessions() as db:
        return list(
            await db.scalars(
                select(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada.like("VINCULO_%"))
                .order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )


def solicitud_pago(did):
    return {
        "departamento_id": did,
        "banco": "YAPE",
        "numero_operacion": "CON05-" + uuid4().hex,
        "fecha_operacion": datetime.now(UTC).date().isoformat(),
        "monto": "25.50",
        "url_voucher": "https://ejemplo.test/voucher-con05.jpg",
    }


def solicitud_reserva(base, did):
    return {
        "departamento_id": did,
        "condominio_id": base.cid,
        "area_id": "11111111-1111-1111-1111-111111111101",
        "fecha_reserva": (datetime.now(UTC).date() + timedelta(days=10)).isoformat(),
        "hora_inicio": "14:00",
        "hora_fin": "16:00",
    }


async def test_relaciones_mixtas_portal_real_y_operaciones_autorizadas(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    anterior = await login(client, A, "Residente123!")
    assert (await vincular(caso)).status_code == 200
    assert (await vincular(caso, B, 1)).status_code == 200
    assert (await vincular(caso, A, 1, "INQUILINO")).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401
    nuevo = await login(client, A, "Residente123!")
    perfil = (await client.get("/api/v1/auth/me", headers=nuevo)).json()
    relaciones = {v["departamento_id"]: v["tipo_relacion"] for v in perfil["departamentos"]}
    assert (
        relaciones[caso["unidades"][0]] == TITULAR
        and relaciones[caso["unidades"][1]] == "INQUILINO"
    )
    catalogo = (await client.get("/api/v1/cuotas/departamentos", headers=nuevo)).json()
    assert {d["id"] for d in catalogo} == set(relaciones)
    assert all(
        d["edificio_nombre"] == "Bloque CON-05" for d in catalogo if d["id"] in caso["unidades"]
    )
    did = caso["unidades"][1]
    assert (
        await client.post("/api/v1/pagos/reportar", headers=nuevo, json=solicitud_pago(did))
    ).status_code == 202
    reserva = await client.post(
        "/api/v1/reservas", headers=nuevo, json=solicitud_reserva(base, did)
    )
    assert reserva.status_code == 201, reserva.text
    assert (await client.delete(ruta(caso, A, 1), headers=admin)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=nuevo)).status_code == 401
    renovado = await login(client, A, "Residente123!")
    assert (
        await client.post("/api/v1/pagos/reportar", headers=renovado, json=solicitud_pago(did))
    ).status_code == 403
    assert (
        await client.post("/api/v1/reservas", headers=renovado, json=solicitud_reserva(base, did))
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/reservas/{reserva.json()['id']}/cancelar", headers=renovado)
    ).status_code == 403
    assert (await client.get("/api/v1/pagos/comprobantes", headers=renovado)).json() == []
    assert (
        len(
            (
                await client.get(
                    f"/api/v1/pagos/comprobantes?condominio_id={base.cid}", headers=admin
                )
            ).json()
        )
        == 1
    )
    assert len(reservas.RESERVAS_REGISTRADAS) == 1


@pytest.mark.parametrize("relacion", ["INQUILINO", "COPROPIETARIO"])
async def test_primera_relacion_exige_titular(caso, relacion):
    response = await vincular(caso, relacion=relacion)
    assert response.status_code == 409 and response.json()["error_code"] == "TITULAR_REQUERIDO"
    async with caso["base"].sessions() as db:
        assert (await db.get(Usuario, id_demo(A))).auth_revision == 1
        assert (
            await db.scalar(
                select(UsuarioDepartamento.id).where(
                    UsuarioDepartamento.departamento_id == UUID(caso["unidades"][0])
                )
            )
            is None
        )
    assert await logs_vinculos(caso["base"]) == []


async def test_ultimo_titular_y_traspaso_sin_perder_identidad(caso):
    client, admin = caso["client"], caso["admin"]
    original = (await vincular(caso)).json()
    for relacion in ("INQUILINO", "COPROPIETARIO"):
        assert (await vincular(caso, relacion=relacion)).status_code == 409
    assert (await client.delete(ruta(caso), headers=admin)).status_code == 409
    assert (await vincular(caso, B)).status_code == 200
    cambiado = await vincular(caso, relacion="INQUILINO")
    assert cambiado.status_code == 200 and cambiado.json()["id"] == original["id"]
    assert (await client.delete(ruta(caso, B), headers=admin)).status_code == 409
    await vincular(caso)
    assert (await client.delete(ruta(caso, B), headers=admin)).status_code == 200


async def test_noop_revocacion_restauracion_auditoria_y_seed(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    await vincular(caso)
    original = (await vincular(caso, B, relacion="INQUILINO")).json()
    await vincular(caso, B, relacion="INQUILINO")
    anterior = await login(client, B, "Inquilino123!")
    for _ in range(2):
        resultado = await client.delete(ruta(caso, B), headers=admin)
        assert resultado.status_code == 200 and resultado.json()["id"] == original["id"]
    # La carga demo no restablece la relación revocada.
    from scripts.seed_usuarios_demo import cargar_demo

    async with base.sessions() as db, db.begin():
        assert await cargar_demo(db) == 0
        assert (await db.get(Usuario, id_demo(B))).auth_revision == 3
    restaurado = await vincular(caso, B, relacion="COPROPIETARIO")
    assert restaurado.json()["id"] == original["id"]
    assert (await client.get("/api/v1/auth/me", headers=anterior)).status_code == 401
    nuevo = await login(client, B, "Inquilino123!")
    assert any(
        v["departamento_id"] == caso["unidades"][0] and v["tipo_relacion"] == "COPROPIETARIO"
        for v in (await client.get("/api/v1/auth/me", headers=nuevo)).json()["departamentos"]
    )
    logs = await logs_vinculos(base)
    assert [log.accion_ejecutada for log in logs] == [
        "VINCULO_CREADO",
        "VINCULO_CREADO",
        "VINCULO_REVOCADO",
        "VINCULO_CAMBIADO",
    ]
    assert all(log.departamento_id == UUID(caso["unidades"][0]) for log in logs)
    assert logs[-1].hash_previo == logs[-2].hash_actual
    assert logs[-1].estado_anterior["es_activo"] is False
    assert logs[-1].estado_posterior["tipo_relacion"] == "COPROPIETARIO"


@pytest.mark.parametrize(
    "email,password", [(A, "Residente123!"), ("auditor@villabonita3.pe", "Auditor123!")]
)
async def test_no_administrativos_no_gestionan_tenencia(caso, email, password):
    client = caso["client"]
    headers = await login(client, email, password)
    assert (await client.get(ruta(caso, unidad=None), headers=headers)).status_code == 403
    assert (await vincular(caso, actor=headers)).status_code == 403
    assert (await client.delete(ruta(caso), headers=headers)).status_code == 403


async def test_junta_gestiona_su_contexto_y_auditoria_con_actor_real(caso):
    client, base = caso["client"], caso["base"]
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    assert (await vincular(caso, actor=junta)).status_code == 200
    logs = await logs_vinculos(base)
    assert logs[0].actor_tipo == "ADMIN_JUNTA" and logs[0].actor_id == str(
        id_demo("admin@villabonita3.pe")
    )
    assert (await client.get(ruta(caso, unidad=None), headers=junta)).status_code == 200


async def test_aislamiento_de_usuario_unidad_y_condominio(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    otro = await otro_condominio(base)
    ajenas = await estructura(client, str(otro), admin, "Bloque ajeno")
    ajeno = ruta(caso).rsplit("/", 1)[0] + "/" + ajenas[0]
    assert (
        await client.put(ajeno, headers=admin, json={"tipo_relacion": TITULAR})
    ).status_code == 404
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    assert (
        await client.put(ruta(caso, cid=otro), headers=junta, json={"tipo_relacion": TITULAR})
    ).status_code == 403
    foreign = await client.post(f"/api/v1/condominios/{otro}/usuarios", headers=admin, json=datos())
    assert (
        await client.get(ruta(caso, unidad=None, uid=foreign.json()["id"]), headers=admin)
    ).status_code == 404
    assert (
        await client.put(
            ruta(caso, uid=foreign.json()["id"]), headers=admin, json={"tipo_relacion": TITULAR}
        )
    ).status_code == 404
    await vincular(caso)
    await client.put(
        f"/api/v1/condominios/{otro}/usuarios/{id_demo(A)}/rol",
        headers=admin,
        json={"rol": "RESIDENTE"},
    )
    response = await client.put(
        f"/api/v1/condominios/{otro}/usuarios/{id_demo(A)}/departamentos/{ajenas[0]}",
        headers=admin,
        json={"tipo_relacion": TITULAR},
    )
    assert response.status_code == 200
    local = (await client.get(ruta(caso, unidad=None), headers=admin)).json()
    assert all(v["condominio_id"] == base.cid and v["departamento_id"] != ajenas[0] for v in local)
    elegido = await login(client, A, "Residente123!", condominio_id=base.cid)
    assert all(
        d["condominio_id"] == base.cid
        for d in (await client.get("/api/v1/cuotas/departamentos", headers=elegido)).json()
    )


async def test_rol_revocado_no_asigna_pero_permite_retirar_inquilino(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    await vincular(caso)
    await vincular(caso, B, relacion="INQUILINO")
    await client.delete(f"/api/v1/condominios/{base.cid}/usuarios/{id_demo(B)}/rol", headers=admin)
    response = await vincular(caso, B, 1)
    assert response.status_code == 409 and response.json()["error_code"] == "ROL_NO_VIGENTE"
    assert (await client.delete(ruta(caso, B), headers=admin)).status_code == 200
    # El titular registrado cuenta aunque su propia autorización haya sido revocada.
    await client.delete(f"/api/v1/condominios/{base.cid}/usuarios/{id_demo(A)}/rol", headers=admin)
    assert (
        await vincular(caso, "auditor@villabonita3.pe", relacion="INQUILINO")
    ).status_code == 200


async def test_cuenta_inactiva_puede_registrar_tenencia_sin_habilitar_acceso(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    nueva = await client.post(
        f"/api/v1/condominios/{base.cid}/usuarios", headers=admin, json=datos()
    )
    uid = nueva.json()["id"]
    response = await client.put(ruta(caso, uid=uid), headers=admin, json={"tipo_relacion": TITULAR})
    assert response.status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": datos()["email"], "password": datos()["password"]}
        )
    ).status_code == 401


async def test_unidad_inactiva_no_autoriza_y_restaura_la_misma_relacion(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    await vincular(caso)
    original = (await vincular(caso, B, relacion="INQUILINO")).json()
    residente = await login(client, B, "Inquilino123!")
    estado = f"/api/v1/condominios/{base.cid}/departamentos/{caso['unidades'][0]}/estado"
    assert (await client.patch(estado, headers=admin, json={"activo": False})).status_code == 200
    assert caso["unidades"][0] not in {
        d["id"]
        for d in (await client.get("/api/v1/cuotas/departamentos", headers=residente)).json()
    }
    assert (
        await client.post(
            "/api/v1/pagos/reportar", headers=residente, json=solicitud_pago(caso["unidades"][0])
        )
    ).status_code == 403
    assert (await client.delete(ruta(caso, B), headers=admin)).status_code == 200
    response = await vincular(caso, B, relacion="INQUILINO")
    assert response.status_code == 409 and response.json()["error_code"] == "DEPARTAMENTO_INACTIVO"
    await client.patch(estado, headers=admin, json={"activo": True})
    assert (await vincular(caso, B, relacion="INQUILINO")).json()["id"] == original["id"]


async def test_put_identico_concurrente_un_solo_vinculo(caso):
    respuestas = await asyncio.gather(vincular(caso), vincular(caso))
    assert [r.status_code for r in respuestas] == [200, 200]
    assert respuestas[0].json()["id"] == respuestas[1].json()["id"]
    assert len(await logs_vinculos(caso["base"])) == 1
    async with caso["base"].sessions() as db:
        assert (await db.get(Usuario, id_demo(A))).auth_revision == 2


@pytest.mark.parametrize("operacion", ["DELETE", "PUT"])
async def test_titulares_concurrentes_no_dejan_la_unidad_sin_titular(caso, operacion):
    await vincular(caso)
    await vincular(caso, B)
    client, admin = caso["client"], caso["admin"]
    requests = [
        client.delete(ruta(caso, email), headers=admin)
        if operacion == "DELETE"
        else vincular(caso, email, relacion="INQUILINO")
        for email in (A, B)
    ]
    respuestas = await asyncio.gather(*requests)
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    async with caso["base"].sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioDepartamento)
                .where(
                    UsuarioDepartamento.departamento_id == UUID(caso["unidades"][0]),
                    UsuarioDepartamento.es_activo.is_(True),
                    UsuarioDepartamento.tipo_relacion == TITULAR,
                )
            )
            == 1
        )


async def test_fallo_auditoria_revierte_vinculos_y_revision(caso):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    await vincular(caso)
    await vincular(caso, B)
    async with base.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE FUNCTION fallo_vinculos() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Fallo controlado'; END; $$"
            )
        )
        await conn.execute(
            text(
                "CREATE TRIGGER fallo_vinculos BEFORE INSERT ON auditoria_logs FOR EACH ROW EXECUTE FUNCTION fallo_vinculos()"
            )
        )
    assert (await vincular(caso, relacion="INQUILINO")).status_code == 500
    assert (await client.delete(ruta(caso), headers=admin)).status_code == 500
    assert (await vincular(caso, "auditor@villabonita3.pe")).status_code == 500
    async with base.sessions() as db:
        assert (await db.get(Usuario, id_demo(A))).auth_revision == 2
        assert (await db.get(Usuario, id_demo("auditor@villabonita3.pe"))).auth_revision == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(UsuarioDepartamento)
                .where(UsuarioDepartamento.departamento_id == UUID(caso["unidades"][0]))
            )
            == 2
        )
    assert len(await logs_vinculos(base)) == 2


async def test_revalida_administrador_revocado_mientras_espera(caso, monkeypatch):
    client, base, admin = caso["client"], caso["base"], caso["admin"]
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    esperando = asyncio.Event()
    original = SQLAlchemyUsuariosRepository.por_id

    async def por_id(repo, uid, *, bloquear=False):
        if uid == id_demo(A) and bloquear:
            esperando.set()
        return await original(repo, uid, bloquear=bloquear)

    monkeypatch.setattr(SQLAlchemyUsuariosRepository, "por_id", por_id)
    async with base.sessions() as db:
        await db.execute(select(Usuario).where(Usuario.id == id_demo(A)).with_for_update())
        pendiente = asyncio.create_task(vincular(caso, actor=junta))
        try:
            await asyncio.wait_for(esperando.wait(), timeout=10)
            assert (
                await client.delete(
                    f"/api/v1/condominios/{base.cid}/usuarios/{id_demo('admin@villabonita3.pe')}/rol",
                    headers=admin,
                )
            ).status_code == 200
        finally:
            await db.rollback()
        assert (await asyncio.wait_for(pendiente, timeout=10)).status_code == 401
    assert await logs_vinculos(base) == []


@pytest.mark.parametrize(
    "body",
    [
        {"tipo_relacion": "PROPIETARIO"},
        {"tipo_relacion": "ADMIN_JUNTA"},
        {"tipo_relacion": None},
        {"tipo_relacion": TITULAR, "es_activo": True},
        {"tipo_relacion": TITULAR, "actor_id": "falso"},
    ],
)
async def test_validacion_y_rechazo_de_campos_extra(caso, body):
    response = await caso["client"].put(ruta(caso), headers=caso["admin"], json=body)
    assert (
        response.status_code == 422 and response.json()["error_code"] == "DATOS_VINCULO_INVALIDOS"
    )


async def test_inexistentes_y_sin_autenticacion(caso):
    client, admin = caso["client"], caso["admin"]
    assert (await client.get(ruta(caso, unidad=None))).status_code == 401
    assert (await client.delete(ruta(caso), headers=admin)).status_code == 404
    inexistente = ruta(caso).rsplit("/", 1)[0] + "/" + str(uuid4())
    assert (
        await client.put(inexistente, headers=admin, json={"tipo_relacion": TITULAR})
    ).status_code == 404
    assert (
        await client.get(ruta(caso, unidad=None, uid=uuid4()), headers=admin)
    ).status_code == 404
    invalido = await client.put(
        ruta(caso).rsplit("/", 1)[0] + "/sin-uuid", headers=admin, json={"tipo_relacion": TITULAR}
    )
    assert (
        invalido.status_code == 422 and invalido.json()["error_code"] == "DATOS_VINCULO_INVALIDOS"
    )


async def test_portal_calcula_deuda_solo_de_cuotas_sql_vencidas(caso):
    base, client = caso["base"], caso["client"]
    await vincular(caso)
    hoy = datetime.now(UTC).date()
    async with base.sessions() as db, db.begin():
        for periodo, total, pagado, vence in [
            ("2026-01", "100.25", "40.10", hoy - timedelta(days=1)),
            ("2026-02", "50.00", "50.00", hoy - timedelta(days=1)),
            ("2026-03", "100.00", "0.00", hoy + timedelta(days=1)),
        ]:
            db.add(
                CuotaMantenimiento(
                    departamento_id=UUID(caso["unidades"][0]),
                    periodo=periodo,
                    monto_ordinario=Decimal(total),
                    monto_total_exigible=Decimal(total),
                    monto_pagado=Decimal(pagado),
                    fecha_emision=hoy - timedelta(days=10),
                    fecha_vencimiento=vence,
                    estado="EMITIDA",
                )
            )
    residente = await login(client, A, "Residente123!")
    catalogo = (await client.get("/api/v1/cuotas/departamentos", headers=residente)).json()
    unidad = next(d for d in catalogo if d["id"] == caso["unidades"][0])
    assert Decimal(unidad["deuda_vencida"]) == Decimal("60.15")


async def test_migracion_indice_preserva_relaciones(db_usuarios):
    base = db_usuarios
    revision = import_module("migrations.versions.20261020_0009_vinculos_departamentos")

    def operar(conn, operation):
        with Operations.context(MigrationContext.configure(conn)):
            operation()

    async with base.engine.begin() as conn:
        ids = list(
            (await conn.execute(text("SELECT id FROM usuario_departamentos ORDER BY id"))).scalars()
        )
        await conn.run_sync(lambda c: operar(c, revision.downgrade))
        await conn.run_sync(lambda c: operar(c, revision.upgrade))
        assert ids == list(
            (await conn.execute(text("SELECT id FROM usuario_departamentos ORDER BY id"))).scalars()
        )
        indices = await conn.run_sync(lambda c: inspect(c).get_indexes("usuario_departamentos"))
        assert "idx_vinculos_titulares_activos" in {indice["name"] for indice in indices}
