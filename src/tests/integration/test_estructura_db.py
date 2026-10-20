"""CON-3 sobre migraciones y PostgreSQL real, aislado mediante esquema/transacción.

CON3_TEST_DATABASE_URL (o la CON13_TEST_DATABASE_URL de CI) debe apuntar a pruebas.
"""

import asyncio
import os
from importlib import import_module
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.core.database import get_db_session
from src.core.models_audit import AuditoriaLogORM
from src.core.security import create_access_token
from src.main import app
from src.modules.condominios.estructura.repository import EstructuraRepository
from src.modules.condominios.models import Departamento
from src.modules.cuotas.distribucion.repository import SQLAlchemyDistribucionRepository

REVISIONES = (
    "20261008_0001_crear_condominios_y_auditoria",
    "20261008_0002_crear_presupuestos_mensuales",
    "20261014_0003_crear_configuracion_distribucion",
    "20261014_0004_crear_aplicaciones_saldo_favor",
    "20261018_0005_estructura_inmobiliaria",
)


def migrar(connection, revisiones=REVISIONES):
    with Operations.context(MigrationContext.configure(connection)):
        for revision in revisiones:
            import_module(f"migrations.versions.{revision}").upgrade()


@pytest_asyncio.fixture
async def connection():
    url = os.environ.get("CON3_TEST_DATABASE_URL") or os.environ.get("CON13_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina CON3_TEST_DATABASE_URL para ejecutar integración PostgreSQL.")
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        transaccion = await conn.begin()
        try:
            esquema = f"con3_{uuid4().hex}"
            await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            yield conn
        finally:
            await transaccion.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def api(connection):
    await connection.run_sync(migrar)
    await connection.run_sync(lambda c: migrar(c, ("20261019_0006_emision_cuotas",)))

    async def db():
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, connection
    app.dependency_overrides.pop(get_db_session, None)


def auth(rol="SUPERADMIN", condominio_id=None):
    return {
        "Authorization": "Bearer "
        + create_access_token(
            {
                "sub": "con3-test",
                "rol": rol,
                "condominio_id": str(condominio_id) if condominio_id else None,
            }
        )
    }


async def condominio(client, nombre="Condominio prueba"):
    respuesta = await client.post(
        "/api/v1/condominios",
        headers=auth(),
        json={
            "nombre": nombre,
            "direccion": "Prueba",
            "moneda": "PEN",
            "regla_mora_tipo": "MONTO_FIJO",
            "monto_mora_fijo": "0.00",
            "dia_vencimiento": 20,
            "dias_gracia": 2,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


async def edificio(client, cid, nombre="Torre A"):
    response = await client.post(
        f"/api/v1/condominios/{cid}/edificios",
        headers=auth(),
        json={"nombre_bloque": nombre, "total_pisos": 14},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_registro_aislamiento_estado_activos_y_auditoria(api):
    client, conn = api
    cid, otro = await condominio(client), await condominio(client, "Otro")
    torre_a, torre_b = await edificio(client, cid), await edificio(client, cid, "Torre B")
    ruta = f"/api/v1/condominios/{cid}"
    datos = {"numero": " 001b ", "piso": 1, "coeficiente_participacion": "50.0000"}
    response = await client.post(
        f"{ruta}/edificios/{torre_a}/departamentos", headers=auth(), json=datos
    )
    assert response.status_code == 201, response.text
    unidad = response.json()
    assert unidad["activo"] is True and unidad["numero"] == "001B"
    assert unidad["saldo_a_favor"] == "0.00" and unidad["coeficiente_participacion"] == "50.0000"
    assert (
        await client.post(f"{ruta}/edificios/{torre_a}/departamentos", headers=auth(), json=datos)
    ).status_code == 409
    assert (
        await client.post(f"{ruta}/edificios/{torre_b}/departamentos", headers=auth(), json=datos)
    ).status_code == 201
    assert (
        await client.post(
            f"{ruta}/edificios",
            headers=auth(),
            json={"nombre_bloque": " torre a ", "total_pisos": 2},
        )
    ).status_code == 409
    assert (
        await client.post(
            f"{ruta}/edificios/{torre_a}/departamentos",
            headers=auth(),
            json={**datos, "numero": "2", "piso": 15},
        )
    ).status_code == 422
    assert (await client.get(f"{ruta}/departamentos")).status_code == 401
    assert (
        await client.get(f"{ruta}/departamentos", headers=auth("ADMIN_JUNTA", otro))
    ).status_code == 403
    assert (
        await client.get(f"{ruta}/departamentos?edificio_id={uuid4()}", headers=auth())
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/condominios/{otro}/departamentos", headers=auth())
    ).json() == []
    estado = f"{ruta}/departamentos/{unidad['id']}/estado"
    assert (
        await client.patch(estado, headers=auth("AUDITOR", cid), json={"activo": False})
    ).status_code == 403
    assert (
        await client.patch(estado, headers=auth("ADMIN_JUNTA", cid), json={"activo": False})
    ).json()["activo"] is False
    assert (await client.patch(estado, headers=auth(), json={"activo": False})).status_code == 200
    assert (
        len(
            (
                await client.get(f"{ruta}/departamentos?activo=true", headers=auth("AUDITOR", cid))
            ).json()
        )
        == 1
    )
    async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint") as session:
        activos = await SQLAlchemyDistribucionRepository(
            session
        ).listar_departamentos_para_distribucion(UUID(cid))
        assert len(activos) == 1 and activos[0].id != UUID(unidad["id"])
        auditorias = list(
            (
                await session.execute(
                    select(AuditoriaLogORM)
                    .where(AuditoriaLogORM.condominio_id == UUID(cid))
                    .order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
                )
            ).scalars()
        )
        assert len(auditorias) == 6  # condominio, dos torres, dos unidades, un cambio real
        for anterior, posterior in zip(auditorias, auditorias[1:]):
            assert posterior.hash_previo == anterior.hash_actual


@pytest.mark.asyncio
async def test_csv_parcial_preview_reintento_conflictos_y_estado_conservado(api):
    client, conn = api
    cid = await condominio(client)
    ruta = f"/api/v1/condominios/{cid}"
    csv = b'numero,piso,edificio,coeficiente,total_pisos\n101,1,"Torre, Norte",50,14\n102,2,"Torre, Norte",50,14\n103,15,"Torre, Norte",1,14\n101,1,"Torre, Norte",50,14\n'

    async def cargar(contenido, confirmar=False):
        return await client.post(
            f"{ruta}/importaciones/{'confirmar' if confirmar else 'previsualizar'}",
            headers=auth(),
            files={"archivo": ("unidades.csv", contenido, "text/csv")},
        )

    preview = (await cargar(csv)).json()
    assert (preview["nuevas"], preview["ya_existentes"], preview["rechazadas"]) == (2, 1, 1)
    assert (await client.get(f"{ruta}/edificios", headers=auth())).json() == []
    resultado = (await cargar(csv, True)).json()
    assert (resultado["creadas"], resultado["ya_existentes"], resultado["rechazadas"]) == (2, 1, 1)
    unidades = (await client.get(f"{ruta}/departamentos", headers=auth())).json()
    uid = unidades[0]["id"]
    await client.patch(f"{ruta}/departamentos/{uid}/estado", headers=auth(), json={"activo": False})
    await conn.execute(
        text(
            "UPDATE departamentos SET saldo_a_favor=12.34, estado_financiero='EN_MORA' WHERE id=:id"
        ),
        {"id": UUID(uid)},
    )
    repetido = (await cargar(csv, True)).json()
    assert repetido["creadas"] == 0 and repetido["ya_existentes"] == 3
    guardado = next(
        d
        for d in (await client.get(f"{ruta}/departamentos", headers=auth())).json()
        if d["id"] == uid
    )
    assert (
        guardado["activo"] is False
        and guardado["saldo_a_favor"] == "12.34"
        and guardado["estado_financiero"] == "EN_MORA"
    )
    conflicto = (
        await cargar(b'numero,piso,edificio,coeficiente\n101,2,"Torre, Norte",40\n', True)
    ).json()
    assert conflicto["rechazadas"] == 1 and conflicto["creadas"] == 0


@pytest.mark.asyncio
async def test_revalida_confirmacion_y_revierte_fallo_auditoria(api, monkeypatch):
    client, conn = api
    cid = await condominio(client)
    ruta = f"/api/v1/condominios/{cid}"
    contenido = b"numero,piso,edificio,coeficiente,total_pisos\n101,1,Norte,100,1\n"

    async def cargar(confirmar):
        return await client.post(
            f"{ruta}/importaciones/{'confirmar' if confirmar else 'previsualizar'}",
            headers=auth(),
            files={"archivo": ("a.csv", contenido)},
        )

    assert (await cargar(False)).json()["nuevas"] == 1
    await cargar(True)
    assert (await cargar(True)).json()["ya_existentes"] == 1
    torre = await edificio(client, cid, "Sur")
    guardar = EstructuraRepository.guardar

    async def fallar(self, recurso, auditoria):
        await guardar(self, recurso, auditoria)
        raise RuntimeError("Fallo auditado")

    monkeypatch.setattr(EstructuraRepository, "guardar", fallar)
    with pytest.raises(RuntimeError, match="Fallo auditado"):
        await client.post(
            f"{ruta}/edificios/{torre}/departamentos",
            headers=auth(),
            json={"numero": "999", "piso": 1, "coeficiente_participacion": "1"},
        )
    assert (
        await conn.scalar(
            select(func.count()).select_from(Departamento).where(Departamento.numero == "999")
        )
        == 0
    )


@pytest.mark.asyncio
async def test_adopta_esquema_backup_conserva_registros_y_downgrade(connection):
    await connection.run_sync(lambda c: migrar(c, REVISIONES[:-1]))
    # Definiciones anteriores a CON-3, como en el backup: relación por edificio y sin activo.
    ddl = [
        "CREATE TABLE edificios (id uuid PRIMARY KEY, condominio_id uuid NOT NULL REFERENCES condominios(id) ON DELETE CASCADE, nombre_bloque varchar(100) NOT NULL, total_pisos integer NOT NULL, CONSTRAINT uq_edificio_condominio_bloque UNIQUE(condominio_id,nombre_bloque), CONSTRAINT ck_edificio_pisos CHECK(total_pisos>=1))",
        "CREATE TABLE departamentos (id uuid PRIMARY KEY, edificio_id uuid NOT NULL REFERENCES edificios(id) ON DELETE CASCADE, numero varchar(20) NOT NULL, piso smallint NOT NULL, coeficiente_participacion numeric(7,4) NOT NULL, saldo_a_favor numeric(12,2) NOT NULL DEFAULT 0, estado_financiero varchar(20) NOT NULL DEFAULT 'AL_DIA', CONSTRAINT uq_edificio_departamento UNIQUE(edificio_id,numero), CONSTRAINT ck_departamento_piso CHECK(piso>=1), CONSTRAINT ck_departamento_coeficiente CHECK(coeficiente_participacion>0.0000), CONSTRAINT ck_departamento_saldo_favor CHECK(saldo_a_favor>=0.00), CONSTRAINT ck_departamento_estado_financiero CHECK(estado_financiero IN ('AL_DIA','OBSERVADO','EN_MORA')))",
        "INSERT INTO condominios(id,nombre,direccion,moneda,regla_mora_tipo,monto_mora_fijo,dia_vencimiento,dias_gracia) VALUES(gen_random_uuid(),'Legado','Prueba','PEN','MONTO_FIJO',0,20,2)",
        "INSERT INTO edificios SELECT gen_random_uuid(),id,'Torre existente',14 FROM condominios",
        "INSERT INTO departamentos SELECT gen_random_uuid(),id,'001',1,0.7200,25.00,'EN_MORA' FROM edificios",
    ]
    for sql in ddl:
        await connection.execute(text(sql))
    previo = (
        await connection.execute(
            text("SELECT id,edificio_id,saldo_a_favor,estado_financiero FROM departamentos")
        )
    ).one()
    await connection.run_sync(lambda c: migrar(c, REVISIONES[-1:]))
    assert await connection.scalar(text("SELECT activo FROM departamentos")) is True
    posterior = (
        await connection.execute(
            text("SELECT id,edificio_id,saldo_a_favor,estado_financiero FROM departamentos")
        )
    ).one()
    assert previo == posterior

    def revertir(c):
        with Operations.context(MigrationContext.configure(c)):
            import_module(f"migrations.versions.{REVISIONES[-1]}").downgrade()
        assert {"edificios", "departamentos"}.issubset(inspect(c).get_table_names())

    await connection.run_sync(revertir)
    assert (
        await connection.scalar(text("SELECT saldo_a_favor FROM departamentos"))
        == previo.saldo_a_favor
    )


@pytest.mark.asyncio
async def test_emisor_usa_unidades_activas_y_contexto_real(api):
    client, _ = api
    for _ in range(2):
        cid = await condominio(client)
        eid = await edificio(client, cid)
        ruta = f"/api/v1/condominios/{cid}"
        for numero in ("101", "102"):
            response = await client.post(
                f"{ruta}/edificios/{eid}/departamentos",
                headers=auth(),
                json={"numero": numero, "piso": 1, "coeficiente_participacion": "100"},
            )
            assert response.status_code == 201
            if numero == "102":
                await client.patch(
                    f"{ruta}/departamentos/{response.json()['id']}/estado",
                    headers=auth(),
                    json={"activo": False},
                )
        presupuesto = await client.post(
            "/api/v1/presupuestos",
            headers=auth(),
            json={
                "condominio_id": cid,
                "periodo": "2026-11",
                "moneda": "PEN",
                "monto_total": "100.00",
                "fecha_vencimiento": "2026-11-20",
            },
        )
        assert presupuesto.status_code == 201, presupuesto.text
        aprobacion = await client.post(
            f"/api/v1/presupuestos/{presupuesto.json()['id']}/aprobar", headers=auth()
        )
        assert aprobacion.status_code == 200, aprobacion.text
        configuracion = await client.put(
            f"/api/v1/condominios/{cid}/distribucion",
            headers=auth(),
            json={"metodo": "POR_ALICUOTA"},
        )
        assert configuracion.status_code == 200, configuracion.text
        datos = {"condominio_id": cid, "periodo": "2026-11"}
        respuesta = await client.post(
            "/api/v1/cuotas/emitir-lote", headers=auth("ADMIN_JUNTA", cid), json=datos
        )
        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["total_cuotas_emitidas"] == 1
        assert (
            await client.post("/api/v1/cuotas/emitir-lote", headers=auth(), json=datos)
        ).status_code == 409
        assert (
            await client.post(
                "/api/v1/cuotas/emitir-lote", headers=auth("ADMIN_JUNTA", uuid4()), json=datos
            )
        ).status_code == 403


@pytest.mark.asyncio
async def test_importaciones_concurrentes_no_duplican_y_conservan_cadena():
    url = os.environ.get("CON3_TEST_DATABASE_URL") or os.environ.get("CON13_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Se necesita PostgreSQL real para concurrencia.")
    esquema = f"con3_concurrente_{uuid4().hex}"
    administrador = create_async_engine(url)
    async with administrador.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
        await conn.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await conn.run_sync(migrar)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": esquema}})

    async def db():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                yield session

    app.dependency_overrides[get_db_session] = db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cid = await condominio(client)
            contenido = b"numero,piso,edificio,coeficiente,total_pisos\n101,1,Norte,50,2\n102,1,Norte,50,2\n"

            async def cargar():
                return await client.post(
                    f"/api/v1/condominios/{cid}/importaciones/confirmar",
                    headers=auth(),
                    files={"archivo": ("a.csv", contenido)},
                )

            resultados = await asyncio.gather(cargar(), cargar())
            assert all(r.status_code == 200 for r in resultados)
            assert sorted(r.json()["creadas"] for r in resultados) == [0, 2]
            async with AsyncSession(engine) as session:
                assert await session.scalar(select(func.count()).select_from(Departamento)) == 2
                auditorias = list(
                    (
                        await session.execute(
                            select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp)
                        )
                    ).scalars()
                )
                assert len(auditorias) == 4
                for anterior, posterior in zip(auditorias, auditorias[1:]):
                    assert posterior.hash_previo == anterior.hash_actual
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()
        async with administrador.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{esquema}" CASCADE'))
        await administrador.dispose()
