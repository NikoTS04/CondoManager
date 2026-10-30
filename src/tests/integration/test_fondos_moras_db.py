"""Caja real, cobertura y retroactivos sin sobregiros sobre PostgreSQL migrado."""

import asyncio
import json
import sys
from decimal import Decimal
from importlib import import_module
from io import BytesIO
from pathlib import Path
from textwrap import dedent
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from docx import Document
from jsonschema import Draft202012Validator, FormatChecker
from pypdf import PdfReader
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from src.modules.condominios.models import Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.consumo import consumir
from src.modules.pagos.fondos import FondosMorasService
from src.modules.pagos.fondos_models import (
    AplicacionMoras,
    CobroMoraFondo,
    EventoFondoMorasOutbox,
    MovimientoFondoMoras,
)
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_mora import MovimientoImputacionDiaria
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.worker import evaluar_moras_diarias
from src.shared.fechas import fecha_lima
from src.tests.integration.test_mora_diaria_db import AHORA, HOY, aprobar, reportar
from src.tests.integration.test_mora_diaria_db import diaria as diaria
from src.tests.integration.test_pagos_db import login
from src.tests.integration.test_pagos_db import reportar as reportar_legacy
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


@pytest_asyncio.fixture
async def caja(api_pagos):
    client, base = api_pagos
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    pago = await reportar_legacy(client, residente, monto="200.00")
    await aprobar(client, junta, pago.json()["comprobante_id"])
    async with base.sessions() as db:
        eid = (await db.get(Departamento, did())).edificio_id
    return client, base, junta, residente, eid


async def borrador(client, base, junta, eid, *, monto="20.00", periodo="2026-11", concepto=None):
    if concepto is None:
        r = await client.post(
            f"/api/v1/condominios/{base.cid}/conceptos-presupuestales",
            headers=junta,
            json={
                "codigo": "COR-01",
                "categoria": "IMPREVISTOS_Y_CONTINGENCIAS",
                "descripcion": "Reparación común",
            },
        )
        assert r.status_code == 201, r.text
        concepto = r.json()["id"]
    r = await client.post(
        "/api/v1/presupuestos",
        headers=junta,
        json={
            "condominio_id": base.cid,
            "periodo": periodo,
            "moneda": "PEN",
            "fecha_vencimiento": periodo + "-10",
            "items": [
                {
                    "concepto_id": concepto,
                    "seccion": "EDIFICIO",
                    "monto_periodo": monto,
                    "metodo_asignacion": "DIRECTO_EDIFICIO",
                    "edificio_id": str(eid),
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json(), concepto


async def reservar(client, junta, p, eid, *, monto="20.00", clave=None):
    payload = {
        "version_esperada": p["version"],
        "item_id": p["items"][0]["id"],
        "edificio_id": str(eid),
        "monto": monto,
        "motivo": "Gasto financiado con recaudación conciliada",
    }
    headers = {**junta, "Idempotency-Key": clave or uuid4().hex}
    r = await client.post(
        f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras", headers=headers, json=payload
    )
    return r, payload, headers


async def fondo(client, junta, eid):
    r = await client.get(
        f"/api/v1/edificios/{eid}/fondos-moras?periodo={fecha_lima():%Y-%m}", headers=junta
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_solo_cobro_mora_no_principal_ni_credito(caja):
    client, base, junta, residente, eid = caja
    f = await fondo(client, junta, eid)
    assert f["saldo_disponible"] == f["cobros_netos_periodo"] == "20.00"
    assert f["mora_pendiente_cobro"] == "0.00"
    assert len(f["movimientos"]) == 1
    async with base.sessions() as db:
        assert (await db.get(Departamento, did())).saldo_a_favor == Decimal("30.00")
    assert (
        await client.get(f"/api/v1/edificios/{eid}/fondos-moras", headers=residente)
    ).status_code == 403
    assert (await client.get(f"/api/v1/edificios/{eid}/fondos-moras")).status_code == 401


async def test_conciliacion_legacy_persiste_fuente_del_fondo_sin_duplicarla(api_pagos):
    client, base = api_pagos
    residente = await login(client)
    junta = await login(client, "admin", "Admin123!")
    reporte = await reportar_legacy(client, residente, monto="170.00")
    comprobante_id = UUID(reporte.json()["comprobante_id"])
    ruta = f"/api/v1/pagos/{comprobante_id}/conciliar"
    # Un intérprete limpio registra los modelos en el orden de la aplicación real,
    # sin los imports adicionales del resto de la suite que ocultaban el fallo FK.
    script = dedent("""
        import asyncio, json, sys
        from src.main import app
        from src.core.database import get_db_session
        from httpx import ASGITransport, AsyncClient
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy.pool import NullPool

        async def main():
            engine = create_async_engine(sys.argv[1], poolclass=NullPool,
                connect_args={"server_settings": {"search_path": sys.argv[2]}})
            sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
            async def session():
                async with sessions() as db:
                    try:
                        yield db
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
            app.dependency_overrides[get_db_session] = session
            async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                                   base_url="http://test") as client:
                login = await client.post("/api/v1/auth/login", json={
                    "email": "admin@villabonita3.pe", "password": "Admin123!"})
                assert login.status_code == 200, login.text
                result = await client.post(sys.argv[3], headers={
                    "Authorization": "Bearer " + login.json()["access_token"]},
                    json={"decision": "APROBADO"})
                assert result.status_code == 200, result.text
                print(json.dumps(result.json()))
            await engine.dispose()
        asyncio.run(main())
    """)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        base.url,
        base.esquema,
        ruta,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    assert process.returncode == 0, stderr.decode()
    decision = json.loads(stdout)
    assert decision["monto_imputado"] == "170.00"

    async def movimiento_confirmado():
        async with base.sessions() as db:
            filas = (
                await db.execute(
                    select(MovimientoFondoMoras, ImputacionPago)
                    .join(
                        ImputacionPago,
                        MovimientoFondoMoras.imputacion_legacy_id == ImputacionPago.id,
                    )
                    .where(ImputacionPago.comprobante_id == comprobante_id)
                )
            ).all()
            assert len(filas) == 1
            movimiento, fuente = filas[0]
            assert movimiento.importe == Decimal("20.00")
            assert fuente.monto_aplicado == Decimal("170.00")
            assert movimiento.movimiento_diario_id is None
            return movimiento.id

    original = await movimiento_confirmado()
    repetida = await client.post(ruta, headers=junta, json={"decision": "APROBADO"})
    assert repetida.status_code == 200 and repetida.json() == decision
    assert await movimiento_confirmado() == original


async def test_cobertura_total_idempotencia_aprobacion_emision_y_documento(caja):
    client, base, junta, residente, eid = caja
    p, _ = await borrador(client, base, junta, eid)
    r, payload, headers = await reservar(client, junta, p, eid)
    assert r.status_code == 201, r.text
    ruta = f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras"
    repetido = await client.post(ruta, headers=headers, json=payload)
    assert repetido.status_code == 201 and repetido.json() == r.json()
    assert (
        await client.post(ruta, headers=headers, json=payload | {"monto": "19.00"})
    ).status_code == 409
    f = await fondo(client, junta, eid)
    assert f["saldo_disponible"] == "0.00" and f["saldo_reservado"] == "20.00"
    p_actual = (
        await client.get(f"/api/v1/condominios/{base.cid}/presupuestos/2026-11", headers=junta)
    ).json()
    assert p_actual["version"] == 2 and p_actual["monto_total"] == "0.00"
    assert p_actual["items"][0]["monto_cubierto_moras"] == "20.00"
    aprobado = await client.post(
        f"/api/v1/presupuestos/{p['id']}/aprobar?version_esperada=2", headers=junta
    )
    assert aprobado.status_code == 200, aprobado.text
    f = await fondo(client, junta, eid)
    assert (
        f["saldo_disponible"] == f["saldo_reservado"] == "0.00" and f["total_aplicado"] == "20.00"
    )
    assert f["aplicaciones_confirmadas_periodo"] == "20.00"
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(MovimientoFondoMoras)) == 2
    reporte = (
        await client.get(
            f"/api/v1/presupuestos/{p['id']}/prorrateo?edificio_id={eid}", headers=junta
        )
    ).json()
    a = reporte["items"][0]["asignaciones"][0]
    assert a["monto_bruto"] == a["monto_cubierto_moras"] == "20.00" and a["monto"] == "0.00"
    descarga = await client.get(
        f"/api/v1/presupuestos/{p['id']}/prorrateo/exportar?version=3&formato=docx&edificio_id={eid}",
        headers=residente,
    )
    assert descarga.status_code == 200, descarga.text
    doc = Document(BytesIO(descarga.content))
    texto = " ".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert (
        "Cubierto moras" in texto
        and "Disponible al capturar" in texto
        and "Cargo definitivo" not in texto
    )
    pdf = await client.get(
        f"/api/v1/presupuestos/{p['id']}/prorrateo/exportar?version=3&formato=pdf&edificio_id={eid}",
        headers=residente,
    )
    assert pdf.status_code == 200
    texto_pdf = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert (
        "Cubierto moras" in texto_pdf
        and "Disponible al capturar" in texto_pdf
        and "Cargo definitivo" not in texto_pdf
    )
    assert "movimientos" not in reporte["fondos_moras"][0]
    emitido = await client.post(
        "/api/v1/cuotas/emitir-lote",
        headers=junta,
        json={"condominio_id": base.cid, "periodo": "2026-11"},
    )
    assert emitido.status_code == 201 and emitido.json()["monto_total_facturado"] == "0.00", (
        emitido.text
    )
    async with base.sessions() as db:
        assert (await db.get(Departamento, did())).saldo_a_favor == Decimal("30.00")
    # El snapshot aprobado no cambia al llegar nueva caja.
    nuevo = await reportar_legacy(client, residente, monto="5.00")
    await aprobar(client, junta, nuevo.json()["comprobante_id"])
    assert (
        await client.get(
            f"/api/v1/presupuestos/{p['id']}/prorrateo?edificio_id={eid}", headers=junta
        )
    ).json() == reporte
    liberar = await client.delete(f"{ruta}/{r.json()['id']}?version_esperada=3", headers=junta)
    assert liberar.status_code == 409


async def test_liberar_restituye_neto_y_no_resucita_clave(caja):
    client, base, junta, _, eid = caja
    p, _ = await borrador(client, base, junta, eid)
    r, payload, headers = await reservar(client, junta, p, eid, monto="10.00")
    assert r.status_code == 201, r.text
    ruta = f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras"
    borrar = f"{ruta}/{r.json()['id']}?version_esperada=2"
    assert (await client.delete(borrar, headers=junta)).status_code == 204
    assert (await client.delete(borrar, headers=junta)).status_code == 204
    repetido = await client.post(ruta, headers=headers, json=payload)
    assert repetido.json()["estado"] == "LIBERADA"
    f = await fondo(client, junta, eid)
    assert f["saldo_disponible"] == "20.00" and f["saldo_reservado"] == "0.00"
    p_actual = (
        await client.get(f"/api/v1/condominios/{base.cid}/presupuestos/2026-11", headers=junta)
    ).json()
    assert p_actual["version"] == 3 and p_actual["monto_total"] == "20.00"


async def test_concurrencia_entre_presupuestos_no_sobregira(caja):
    client, base, junta, _, eid = caja
    a, concepto = await borrador(client, base, junta, eid)
    b, _ = await borrador(client, base, junta, eid, periodo="2026-12", concepto=concepto)
    respuestas = await asyncio.gather(
        reservar(client, junta, a, eid, monto="15.00"),
        reservar(client, junta, b, eid, monto="15.00"),
    )
    assert sorted(r[0].status_code for r in respuestas) == [201, 409]
    assert (await fondo(client, junta, eid))["saldo_disponible"] == "5.00"
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AplicacionMoras)) == 1


async def test_no_omitir_item_cubierto_ni_fabricar_cobertura(caja):
    client, base, junta, _, eid = caja
    p, _ = await borrador(client, base, junta, eid)
    r, _, _ = await reservar(client, junta, p, eid)
    assert r.status_code == 201
    body = {k: p[k] for k in ("periodo", "moneda", "fecha_vencimiento", "items")}
    body["version_esperada"] = 2
    # Omite el importe cubierto existente.
    assert (
        await client.put(f"/api/v1/presupuestos/{p['id']}", headers=junta, json=body)
    ).status_code == 422
    body["items"][0]["id"] = str(uuid4())
    error = await client.put(f"/api/v1/presupuestos/{p['id']}", headers=junta, json=body)
    assert error.status_code == 409 and error.json()["error_code"] == "ITEM_CON_COBERTURA"


async def test_retroactivo_comprometido_revierte_todo_y_liberacion_permite_conciliar(diaria):
    client, base, cuota_id = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    await aprobar(client, junta, await reportar(client, residente, 20, "110.00"))
    async with base.sessions() as db:
        eid = (await db.get(Departamento, did())).edificio_id
    p, _ = await borrador(client, base, junta, eid, monto="10.00")
    r, _, _ = await reservar(client, junta, p, eid, monto="10.00")
    assert r.status_code == 201
    retroactivo = await reportar(client, residente, 10, "100.00")
    rechazo = await client.post(
        f"/api/v1/pagos/{retroactivo}/conciliar", headers=junta, json={"decision": "APROBADO"}
    )
    assert (
        rechazo.status_code == 409 and rechazo.json()["error_code"] == "FONDOS_MORAS_COMPROMETIDOS"
    ), rechazo.text
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, UUID(retroactivo))).estado == "EN_REVISION"
        assert (await db.get(CuotaMantenimiento, cuota_id)).monto_mora == Decimal("10.00")
        assert await db.scalar(
            select(func.sum(MovimientoImputacionDiaria.importe)).where(
                MovimientoImputacionDiaria.componente == "MORA"
            )
        ) == Decimal("10.00")
    liberar = await client.delete(
        f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras/{r.json()['id']}?version_esperada=2",
        headers=junta,
    )
    assert liberar.status_code == 204
    await aprobar(client, junta, retroactivo)
    f = await fondo(client, junta, eid)
    assert f["saldo_disponible"] == "0.00"
    assert f["cobros_confirmados_periodo"] == f["reversos_cobro_periodo"] == "10.00"


async def test_eventos_fondos_versionados_y_consumo_interno(caja):
    client, base, junta, _, eid = caja
    p, _ = await borrador(client, base, junta, eid)
    r, _, _ = await reservar(client, junta, p, eid)
    assert r.status_code == 201
    assert (
        await client.delete(
            f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras/{r.json()['id']}?version_esperada=2",
            headers=junta,
        )
    ).status_code == 204
    p["version"] = 3
    assert (await reservar(client, junta, p, eid))[0].status_code == 201
    assert (
        await client.post(
            f"/api/v1/presupuestos/{p['id']}/aprobar?version_esperada=4", headers=junta
        )
    ).status_code == 200
    esquema = json.loads(
        Path("specs/03-contracts/events/schemas/fondos-moras.v1.schema.json").read_text()
    )
    async with base.sessions() as db:
        eventos = list(await db.scalars(select(EventoFondoMorasOutbox)))
    assert len(eventos) == 5
    assert {e.payload["data"]["tipo"] for e in eventos} == {
        "COBRO",
        "RESERVA",
        "LIBERACION",
        "CONFIRMACION",
    }
    for e in eventos:
        Draft202012Validator(esquema, format_checker=FormatChecker()).validate(e.payload)
        assert await consumir(base.sessions, e.payload) == 0
        assert await consumir(base.sessions, e.payload) == 0


async def test_auditor_lectura_y_edificio_ajeno_sin_caja(caja):
    client, base, junta, _, eid = caja
    p, _ = await borrador(client, base, junta, eid)
    auditor = await login(client, "auditor", "Auditor123!")
    assert (
        await client.get(f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras", headers=auditor)
    ).status_code == 200
    assert (await reservar(client, auditor, p, eid))[0].status_code == 403
    async with base.sessions() as db, db.begin():
        otro = Edificio(
            id=uuid4(), condominio_id=UUID(base.cid), nombre_bloque="Sin fondos", total_pisos=1
        )
        db.add(otro)
        otro_id = otro.id
    r, _, _ = await reservar(client, junta, p, otro_id)
    assert r.status_code == 409 and r.json()["error_code"] == "FONDOS_MORAS_INSUFICIENTES"


async def test_cobro_anterior_no_se_adopta_como_caja_historica(diaria, monkeypatch):
    client, base, _ = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")

    async def motor_anterior(*_, **__):
        pass

    with monkeypatch.context() as contexto:
        contexto.setattr(FondosMorasService, "registrar_cobros", motor_anterior)
        await aprobar(client, junta, await reportar(client, residente, 20, "110.00"))
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    async with base.sessions() as db:
        eid = (await db.get(Departamento, did())).edificio_id
        assert (await db.scalar(select(CobroMoraFondo))).base_no_adoptada == Decimal("10.00")
        assert await db.scalar(select(func.count()).select_from(MovimientoFondoMoras)) == 0
    assert (await fondo(client, junta, eid))["saldo_disponible"] == "0.00"
    await aprobar(client, junta, await reportar(client, residente, 10, "100.00"))
    assert (await fondo(client, junta, eid))["saldo_disponible"] == "0.00"


async def test_reverso_conserva_edificio_original_del_cobro(diaria):
    client, base, _ = diaria
    residente, junta = await login(client), await login(client, "admin", "Admin123!")
    await aprobar(client, junta, await reportar(client, residente, 20, "110.00"))
    async with base.sessions() as db, db.begin():
        d = await db.get(Departamento, did())
        original = d.edificio_id
        otro = Edificio(
            id=uuid4(), condominio_id=UUID(base.cid), nombre_bloque="Destino nuevo", total_pisos=1
        )
        db.add(otro)
        await db.flush()
        d.edificio_id = otro.id
        destino = otro.id
    await aprobar(client, junta, await reportar(client, residente, 10, "100.00"))
    async with base.sessions() as db:
        movimientos = list(await db.scalars(select(MovimientoFondoMoras)))
        assert len(movimientos) == 2 and all(m.edificio_id == original for m in movimientos)
    assert (await fondo(client, junta, original))["saldo_disponible"] == "0.00"
    assert (await fondo(client, junta, destino))["saldo_disponible"] == "0.00"


async def test_fallo_auditoria_no_reserva_ni_altera_presupuesto(caja, monkeypatch):
    client, base, junta, _, eid = caja
    p, _ = await borrador(client, base, junta, eid)

    async def fallar(*_, **__):
        raise RuntimeError("Fallo de auditoría de tesorería")

    monkeypatch.setattr(SQLAlchemyPagosRepository, "auditar", fallar)
    with pytest.raises(RuntimeError, match="tesorería"):
        await reservar(client, junta, p, eid)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AplicacionMoras)) == 0
        assert await db.scalar(select(func.count()).select_from(MovimientoFondoMoras)) == 1
    actual = (
        await client.get(f"/api/v1/condominios/{base.cid}/presupuestos/2026-11", headers=junta)
    ).json()
    assert actual["version"] == 1 and actual["monto_total"] == "20.00"


async def test_validaciones_importe_cobertura_motivo_y_periodo(caja):
    client, base, junta, _, eid = caja
    p, _ = await borrador(client, base, junta, eid, monto="10.00")
    for importe in ("11.00", "0.00", "1.001", 1.0):
        r, _, _ = await reservar(client, junta, p, eid, monto=importe)
        assert r.status_code == 422, r.text
    ruta = f"/api/v1/edificios/{eid}/fondos-moras"
    assert (await client.get(ruta + "?periodo=0000-01", headers=junta)).status_code == 422
    assert (await client.get(ruta + "?periodo=9999-12", headers=junta)).status_code == 200
    _, payload, headers = await reservar(client, junta, p, eid, monto="0.00")
    payload["monto"], payload["motivo"] = "1.00", "   "
    assert (
        await client.post(
            f"/api/v1/presupuestos/{p['id']}/aplicaciones-moras", headers=headers, json=payload
        )
    ).status_code == 422
    assert (await fondo(client, junta, eid))["saldo_disponible"] == "20.00"


async def test_ledger_inmutable_y_downgrade_protegido(caja):
    _, base, _, _, _ = caja
    async with base.sessions() as db:
        for sentencia in (
            "UPDATE cobros_mora_fondo SET base_no_adoptada=1",
            "DELETE FROM movimientos_fondo_moras",
        ):
            with pytest.raises(DBAPIError, match="inmutable"):
                await db.execute(text(sentencia))
            await db.rollback()

    def bajar(conn):
        with Operations.context(MigrationContext.configure(conn)):
            import_module("migrations.versions.20261025_0020_fondos_moras").downgrade()

    with pytest.raises(DBAPIError, match="fondos o aplicaciones"):
        async with base.engine.begin() as conn:
            await conn.run_sync(bajar)


async def test_migracion_vacia_reversible_conserva_padron(api_usuarios):
    _, base = api_usuarios

    def ciclo(conn):
        with Operations.context(MigrationContext.configure(conn)):
            migracion = import_module("migrations.versions.20261025_0020_fondos_moras")
            migracion.downgrade()
            migracion.upgrade()

    async with base.engine.begin() as conn:
        await conn.run_sync(ciclo)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Departamento)) > 0
        assert await db.scalar(select(func.count()).select_from(MovimientoFondoMoras)) == 0
