"""CON-25–28: productor real, PostgreSQL, autoflush productivo y consumidores existentes."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import Notificacion
from src.modules.pagos.models import ImputacionPago
from src.modules.pagos.models_persistencia import EventoPagoOutbox, RevisionPago
from src.modules.pagos.persistencia import PagosPersistentesService
from src.tests.integration.test_aislamiento_con77_db import huella
from src.tests.integration.test_pagos_db import imagen
from src.tests.pagos_db import did
from src.tests.pagos_sprint3 import HOY, reportar, revisar
from src.tests.pagos_sprint3 import sistema as sistema

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def cuenta(client, residente):
    r = await client.get(
        f"/api/v1/cuotas/departamentos/{did('102')}/estado-cuenta"
        "?desde=2026-01-01&hasta=2026-12-31",
        headers=residente,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("sistema", [{}, {"diaria": True}], indirect=True)
async def test_aprobacion_exacta_recibo_inmutable_y_reintento_sin_efectos(sistema):
    client, base, cid, residente, junta = sistema
    pid = await reportar(client, residente)
    r = await revisar(client, junta, pid)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "private, no-store"
    data = r.json()
    assert data["monto_imputado"] == "100.00" and data["nuevo_saldo_departamento"] == "0.00"
    antes = await huella(base)
    assert (await revisar(client, junta, pid)).json() == data
    await base.engine.dispose()
    recuperado = await client.get(f"/api/v1/pagos/{pid}/resultado", headers=residente)
    assert recuperado.json() == data
    assert recuperado.headers["cache-control"] == "private, no-store"
    assert "authorization" in {
        token.strip().lower() for token in recuperado.headers["vary"].split(",")
    }
    assert await huella(base) == antes
    c = await cuenta(client, residente)
    assert c["deuda_actual"] == "0.00" and c["abonos_periodo"] == "100.00"


@pytest.mark.parametrize("vencida", [True, False])
async def test_parcial_estado_y_solvencia_hasta_completar(sistema, vencida):
    client, base, cid, residente, junta = sistema
    if not vencida:
        async with base.sessions() as db, db.begin():
            (await db.get(CuotaMantenimiento, cid)).fecha_vencimiento = date(2026, 10, 30)
    pid = await reportar(client, residente, "40.00")
    r = await revisar(client, junta, pid)
    assert r.status_code == 200, r.text
    assert r.json()["nuevo_saldo_departamento"] == "60.00"
    assert r.json()["departamento_habilitado_reservas"] is not vencida
    async with base.sessions() as db:
        cuota = await db.get(CuotaMantenimiento, cid)
        assert cuota.estado == ("EN_MORA" if vencida else "PAGO_PARCIAL")
        assert cuota.monto_total_exigible == Decimal("100.00")
        assert cuota.monto_pagado == Decimal("40.00")
    assert (await cuenta(client, residente))["deuda_actual"] == "60.00"
    final = await revisar(client, junta, await reportar(client, residente, "60.00"))
    assert final.json()["nuevo_saldo_departamento"] == "0.00"
    assert final.json()["departamento_habilitado_reservas"] is True


@pytest.mark.parametrize("sistema", [{}, {"diaria": True}], indirect=True)
async def test_excedente_con_origen_y_consumo_real_con13_una_vez(sistema):
    from src.modules.cuotas.saldos.repository import SQLAlchemySaldoFavorRepository
    from src.modules.cuotas.saldos.service import ActorSaldoFavor, SaldosFavorService

    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente, "120.00")
    r = await revisar(client, junta, pid)
    assert r.status_code == 200, r.text
    assert r.json()["saldo_a_favor_generado"] == "20.00"
    c = await cuenta(client, residente)
    assert c["saldo_a_favor_actual"] == "20.00" and c["abonos_periodo"] == "120.00"
    assert [m["comprobante_id"] for m in c["movimientos"] if m["tipo"] == "PAGO_APROBADO"] == [pid]
    async with base.sessions() as db, db.begin():
        cuota = CuotaMantenimiento(
            id=uuid4(),
            departamento_id=did("102"),
            periodo="2026-11",
            fecha_emision=HOY,
            fecha_vencimiento=date(2026, 11, 10),
            monto_ordinario=Decimal("30.00"),
            monto_total_exigible=Decimal("30.00"),
            monto_pagado=Decimal("0.00"),
            monto_descuento=Decimal("0.00"),
            estado="EMITIDA",
        )
        db.add(cuota)
        await db.flush()
        servicio = SaldosFavorService(SQLAlchemySaldoFavorRepository(db))
        actor = ActorSaldoFavor(str(UUID(int=1)), "ADMIN_JUNTA", UUID(base.cid))
        aplicado = await servicio.aplicar_a_cuota_emitida(cuota, actor)
        repetido = await servicio.aplicar_a_cuota_emitida(cuota, actor)
        assert aplicado.id == repetido.id and aplicado.monto_aplicado == Decimal("20.00")
    await revisar(client, junta, pid)
    c = await cuenta(client, residente)
    assert c["saldo_a_favor_actual"] == "0.00" and c["deuda_actual"] == "10.00"


@pytest.mark.parametrize("decision", ["OBSERVADO", "RECHAZADO"])
async def test_decision_motivo_evento_y_no_acreditacion(sistema, decision):
    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente)
    antes = await huella(base)
    for motivo in (None, "", "   "):
        r = await revisar(client, junta, pid, decision, motivo_rechazo=motivo)
        assert r.status_code == 422
    assert await huella(base) == antes
    campos = {"motivo_rechazo": "  Verifique la operación  ", "notas_internas": "PRIVADO"}
    r = await revisar(client, junta, pid, decision, **campos)
    assert r.status_code == 200, r.text
    assert r.json()["monto_imputado"] == "0.00" and r.json()["nuevo_saldo_departamento"] == "100.00"
    antes = await huella(base)
    assert (await revisar(client, junta, pid, decision, **campos)).json() == r.json()
    assert await huella(base) == antes
    assert (await revisar(client, junta, pid)).status_code == 409
    async with base.sessions() as db:
        eventos = list(await db.scalars(select(EventoPagoOutbox)))
        assert await db.scalar(select(ImputacionPago.id)) is None
    for e in eventos:
        assert await consumir(base.sessions, e.payload) == 1
        assert await consumir(base.sessions, e.payload) == 0
    async with base.sessions() as db:
        avisos = list(await db.scalars(select(Notificacion)))
        assert len(avisos) == 2 and all(a.estado == "EN_COLA" for a in avisos)
        assert all("PRIVADO" not in a.cuerpo for a in avisos)
    assert (await cuenta(client, residente))["deuda_actual"] == "100.00"


async def test_subsanacion_conserva_evidencia_y_rechazo_no_se_reabre(sistema):
    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente)
    await revisar(client, junta, pid, "OBSERVADO", motivo_rechazo="Imagen ilegible")
    historial = (await client.get(f"/api/v1/pagos/{pid}/evidencias", headers=residente)).json()
    r = await client.put(
        f"/api/v1/pagos/{pid}/voucher",
        headers=residente,
        files={"archivo_voucher": ("nueva.png", imagen(), "image/png")},
    )
    assert r.status_code == 202 and r.json()["comprobante_id"] == pid
    assert (
        await client.get(f"/api/v1/pagos/{pid}/resultado", headers=residente)
    ).status_code == 404
    antigua = await client.get(
        f"/api/v1/pagos/{pid}/voucher?evidencia_id={historial[0]['evidencia_id']}",
        headers=residente,
    )
    assert antigua.status_code == 200 and antigua.content == imagen()
    r = await revisar(client, junta, pid, "RECHAZADO", motivo_rechazo="No acreditado")
    assert r.status_code == 200
    antes = await huella(base)
    assert (
        await client.put(
            f"/api/v1/pagos/{pid}/voucher",
            headers=residente,
            files={"archivo_voucher": ("otra.png", imagen(), "image/png")},
        )
    ).status_code == 409
    assert await huella(base) == antes


async def test_resultado_vigente_con_revisiones_en_el_mismo_instante(sistema, monkeypatch):
    client, _, _, residente, junta = sistema
    pid = await reportar(client, residente)
    # Dos revisiones con reloj fijo y UUID inversos: la evidencia vigente manda,
    # no el orden aleatorio del UUID de otra evidencia anterior.
    with monkeypatch.context() as m:
        m.setattr("src.modules.pagos.persistencia.uuid4", lambda: UUID(int=999))
        observado = await revisar(client, junta, pid, "OBSERVADO", motivo_rechazo="Ilegible")
    assert observado.status_code == 200
    r = await client.put(
        f"/api/v1/pagos/{pid}/voucher",
        headers=residente,
        files={"archivo_voucher": ("nueva.png", imagen(), "image/png")},
    )
    assert r.status_code == 202
    with monkeypatch.context() as m:
        m.setattr("src.modules.pagos.persistencia.uuid4", lambda: UUID(int=1))
        rechazado = await revisar(client, junta, pid, "RECHAZADO", motivo_rechazo="No acreditado")
    assert rechazado.status_code == 200
    resultado = await client.get(f"/api/v1/pagos/{pid}/resultado", headers=residente)
    assert resultado.status_code == 200, resultado.text
    assert resultado.json() == rechazado.json()
    assert (
        await revisar(client, junta, pid, "RECHAZADO", motivo_rechazo="No acreditado")
    ).json() == rechazado.json()


@pytest.mark.parametrize("sistema", [{}, {"diaria": True}], indirect=True)
async def test_fallo_tardio_outbox_revierte_todas_las_tablas(sistema, monkeypatch):
    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente, "130.00", "2026-10-20")
    antes = await huella(base)
    original = PagosPersistentesService._evento

    def fallar(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("outbox: fallo posterior a la auditoría")

    with monkeypatch.context() as m:
        m.setattr(PagosPersistentesService, "_evento", fallar)
        assert (await revisar(client, junta, pid)).status_code == 500
    assert await huella(base) == antes
    assert (await revisar(client, junta, pid)).status_code == 200


async def test_decisiones_concurrentes_incompatibles_tienen_un_ganador(sistema):
    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente, "120.00")
    resultados = await asyncio.gather(
        revisar(client, junta, pid),
        revisar(client, junta, pid, "RECHAZADO", motivo_rechazo="No validado"),
    )
    assert sorted(r.status_code for r in resultados) == [200, 409]
    async with base.sessions() as db:
        revisiones = list(await db.scalars(select(RevisionPago)))
        assert len(revisiones) == 1
        assert len(list(await db.scalars(select(EventoPagoOutbox)))) == 2
        d = await db.get(Departamento, did("102"))
        assert d.saldo_a_favor == Decimal(
            "20.00" if revisiones[0].decision == "APROBADO" else "0.00"
        )


@pytest.mark.parametrize("sistema", [{}, {"diaria": True}], indirect=True)
async def test_fecha_bancaria_anterior_a_emision_genera_credito_no_abono(sistema):
    client, base, cid, residente, junta = sistema
    async with base.sessions() as db, db.begin():
        (await db.get(CuotaMantenimiento, cid)).fecha_emision = date(2026, 10, 15)
    pid = await reportar(client, residente)
    r = await revisar(client, junta, pid)
    assert r.status_code == 200, r.text
    assert r.json()["monto_imputado"] == "0.00"
    assert r.json()["saldo_a_favor_generado"] == "100.00"
    async with base.sessions() as db:
        assert (await db.get(CuotaMantenimiento, cid)).monto_pagado == 0


async def test_auditoria_contiene_fotografias_y_cadena(sistema):
    client, base, cid, residente, junta = sistema
    pid = await reportar(client, residente)
    assert (await revisar(client, junta, pid)).status_code == 200
    async with base.sessions() as db:
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        revision = next(a for a in logs if a.accion_ejecutada == "REVISION_PAGO_APROBADO")
        assert revision.estado_anterior["cuotas"][str(cid)]["pagado"] == "0.00"
        assert revision.estado_posterior["cuotas"][str(cid)]["pagado"] == "100.00"
        assert all(b.hash_previo == a.hash_actual for a, b in zip(logs, logs[1:]))


async def test_plan_inconsistente_se_rechaza_y_revierte_credito(sistema, monkeypatch):
    import src.modules.pagos.persistencia as pagos

    client, base, _, residente, junta = sistema
    pid = await reportar(client, residente)
    antes = await huella(base)
    original = pagos.plan_imputacion

    def corrupto(*args, **kwargs):
        plan = original(*args, **kwargs)
        plan["remanente"] += Decimal("0.01")
        return plan

    monkeypatch.setattr(pagos, "plan_imputacion", corrupto)
    r = await revisar(client, junta, pid)
    assert r.status_code == 409 and r.json()["error_code"] == "IMPUTACION_PAGO_INCONSISTENTE"
    assert await huella(base) == antes


@pytest.mark.parametrize("sistema", [{}, {"diaria": True}], indirect=True)
async def test_aprobar_y_emitir_con13_concurrentes_conservan_credito(sistema, monkeypatch):
    from src.modules.condominios.models import Edificio
    from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion
    from src.modules.cuotas.emision import EmisionCuotasService
    from src.modules.cuotas.presupuestos.models import PresupuestoMensual
    from src.modules.cuotas.saldos.service import ActorSaldoFavor
    from src.modules.cuotas.schemas import EmitirLoteRequest
    from src.tests.pagos_sprint3 import RelojPago

    client, base, _, residente, junta = sistema
    monkeypatch.setattr("src.modules.cuotas.emision.fecha_lima", lambda: date(2026, 11, 1))
    async with base.sessions() as db, db.begin():
        departamentos = list(
            await db.scalars(
                select(Departamento)
                .join(Edificio)
                .where(
                    Edificio.condominio_id == UUID(base.cid),
                    Departamento.activo.is_(True),
                )
            )
        )
        config = await db.scalar(
            select(ConfiguracionDistribucion).where(
                ConfiguracionDistribucion.condominio_id == UUID(base.cid),
            )
        )
        if config:
            config.metodo = "EQUITATIVA"
        else:
            db.add(
                ConfiguracionDistribucion(
                    condominio_id=UUID(base.cid),
                    metodo="EQUITATIVA",
                    actualizado_por="prueba",
                    actualizado_en=RelojPago.now(),
                )
            )
        db.add(
            PresupuestoMensual(
                condominio_id=UUID(base.cid),
                periodo="2026-11",
                moneda="PEN",
                monto_total=Decimal("30.00") * len(departamentos),
                fecha_vencimiento=date(2026, 11, 10),
                estado="APROBADO",
                creado_por="prueba",
                aprobado_por="prueba",
                aprobado_en=RelojPago.now(),
            )
        )
    pid = await reportar(client, residente, "120.00")

    async def emitir():
        async with base.sessions() as db:
            return await EmisionCuotasService(db).emitir(
                EmitirLoteRequest(condominio_id=base.cid, periodo="2026-11"),
                ActorSaldoFavor("prueba", "ADMIN_JUNTA", UUID(base.cid)),
            )

    aprobacion, _ = await asyncio.gather(revisar(client, junta, pid), emitir())
    assert aprobacion.status_code == 200, aprobacion.text
    async with base.sessions() as db:
        nueva = await db.scalar(
            select(CuotaMantenimiento).where(
                CuotaMantenimiento.departamento_id == did("102"),
                CuotaMantenimiento.periodo == "2026-11",
            )
        )
        saldo = (await db.get(Departamento, did("102"))).saldo_a_favor
        assert nueva.monto_pagado + saldo == Decimal("20.00")
    assert (await cuenta(client, residente))["saldo_neto_actual"] == "10.00"
