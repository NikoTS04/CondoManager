"""CON-32: avisos de emisión de cuotas desde el outbox real, en PostgreSQL."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.security import hash_password
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.saldos.service import ActorSaldoFavor
from src.modules.cuotas.schemas import EmitirLoteRequest
from src.modules.notificaciones.consumo import MEDIOS_PAGO, consumir
from src.modules.notificaciones.models import EventoConsumido, Notificacion
from src.modules.notificaciones.worker import recuperar_eventos
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
PERIODO = "2026-11"
VENCIMIENTO = date(2026, 11, 20)
EXTRA = "segundo.residente102@villabonita3.pe"


async def emitir_lote(base):
    """Lote real: 139 departamentos a 100.00 cada uno (13900.00 equitativo)."""
    cid = CONDOMINIO_PILOTO_ID
    async with base.sessions() as db, db.begin():
        db.add(
            PresupuestoMensual(
                id=uuid4(),
                condominio_id=cid,
                periodo=PERIODO,
                moneda="PEN",
                monto_total=Decimal("13900.00"),
                fecha_vencimiento=VENCIMIENTO,
                estado="APROBADO",
                creado_por="prueba",
                aprobado_por="prueba",
                aprobado_en=datetime.now(UTC),
            )
        )
        db.add(
            ConfiguracionDistribucion(
                id=uuid4(),
                condominio_id=cid,
                metodo="EQUITATIVA",
                actualizado_por="prueba",
                actualizado_en=datetime.now(UTC),
            )
        )
    async with base.sessions() as db:
        await EmisionCuotasService(db).emitir(
            EmitirLoteRequest(condominio_id=cid, periodo=PERIODO),
            ActorSaldoFavor("prueba", "ADMIN_JUNTA", cid),
        )


async def agregar_segundo_residente(base):
    uid = uuid4()
    async with base.sessions() as db, db.begin():
        db.add(
            Usuario(
                id=uid,
                email=EXTRA,
                password_hash=hash_password("Residente123!"),
                nombre="Mario",
                apellido="Copropietario",
                documento_identidad="DEMO900001",
                esta_activo=True,
                es_superadmin=False,
                auth_revision=1,
                creado_en=datetime.now(UTC),
            )
        )
        await db.flush()
        db.add(UsuarioRol(usuario_id=uid, condominio_id=CONDOMINIO_PILOTO_ID, rol="RESIDENTE"))
        db.add(
            UsuarioDepartamento(
                usuario_id=uid,
                departamento_id=did("102"),
                tipo_relacion="COPROPIETARIO",
                es_activo=True,
            )
        )
    return uid


async def evento_lote(base):
    async with base.sessions() as db:
        return (await db.scalar(select(EventoLoteOutbox))).payload


async def importes(base):
    async with base.sessions() as db:
        filas = await db.execute(
            select(
                CuotaMantenimiento.id,
                CuotaMantenimiento.monto_total_exigible,
                CuotaMantenimiento.monto_pagado,
            ).where(CuotaMantenimiento.periodo == PERIODO)
        )
        return {f.id: (f.monto_total_exigible, f.monto_pagado) for f in filas}


def sesion_nueva(base):
    """Motor y fábrica nuevos: nada de la sesión que emitió se reutiliza al consultar."""
    engine = create_async_engine(
        base.url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": base.esquema}},
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_un_aviso_por_cuota_y_destinatario_con_datos_persistidos(db_usuarios):
    base = db_usuarios
    await emitir_lote(base)
    extra = await agregar_segundo_residente(base)
    payload = await evento_lote(base)
    antes = await importes(base)
    assert len(antes) == 139

    # Departamentos con residente: 102 (dos), 402 y 504.
    assert await consumir(base.sessions, payload) == 4
    assert await consumir(base.sessions, payload) == 0
    assert await recuperar_eventos(base.sessions) is None
    assert await importes(base) == antes

    engine, sessions = sesion_nueva(base)
    try:
        async with sessions() as db:
            logs = list(await db.scalars(select(Notificacion).order_by(Notificacion.destinatario)))
            cuotas = {
                c.departamento_id: c
                for c in await db.scalars(
                    select(CuotaMantenimiento).where(CuotaMantenimiento.periodo == PERIODO)
                )
            }
            usuarios = {u.id: u for u in await db.scalars(select(Usuario))}
            assert await db.scalar(select(func.count()).select_from(EventoConsumido)) == 1
    finally:
        await engine.dispose()

    assert len(logs) == 4
    assert {(log.departamento_id, log.usuario_destinatario_id) for log in logs} == {
        (did("102"), id_demo("residente102@villabonita3.pe")),
        (did("102"), extra),
        (did("402"), id_demo("moroso402@villabonita3.pe")),
        (did("504"), id_demo("inquilino504@villabonita3.pe")),
    }
    for log in logs:
        cuota = cuotas[log.departamento_id]
        assert log.evento_id == UUID(payload["event_id"]) and log.canal == "EMAIL"
        assert log.operacion_id == cuota.id and log.tipo_evento == "NOTIF_EMISION_CUOTA"
        assert log.destinatario == usuarios[log.usuario_destinatario_id].email
        assert log.estado == "EN_COLA" and log.intentos == 0
        numero = {did("102"): "102", did("402"): "402", did("504"): "504"}[log.departamento_id]
        assert PERIODO in log.cuerpo and PERIODO in log.asunto
        assert f"Dpto. {numero}" in log.cuerpo
        assert f"S/ {cuota.monto_total_exigible:.2f}" in log.cuerpo
        assert VENCIMIENTO.isoformat() in log.cuerpo
        assert MEDIOS_PAGO in log.cuerpo
        assert "002-191" not in log.cuerpo and "{" not in log.cuerpo


async def test_usuario_o_vinculo_inactivo_no_recibe_aviso(db_usuarios):
    base = db_usuarios
    await emitir_lote(base)
    async with base.sessions() as db, db.begin():
        moroso = await db.get(Usuario, id_demo("moroso402@villabonita3.pe"))
        moroso.esta_activo = False
        vinculo = await db.scalar(
            select(UsuarioDepartamento).where(
                UsuarioDepartamento.usuario_id == id_demo("residente102@villabonita3.pe")
            )
        )
        vinculo.es_activo = False
    payload = await evento_lote(base)
    assert await consumir(base.sessions, payload) == 1
    await base.engine.dispose()
    async with base.sessions() as db:
        logs = list(await db.scalars(select(Notificacion)))
    assert [log.usuario_destinatario_id for log in logs] == [
        id_demo("inquilino504@villabonita3.pe")
    ]
    assert logs[0].departamento_id == did("504")


async def test_recuperacion_desde_outbox_es_idempotente(db_usuarios):
    base = db_usuarios
    await emitir_lote(base)
    antes = await importes(base)
    await recuperar_eventos(base.sessions)
    await recuperar_eventos(base.sessions)
    await base.engine.dispose()
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 3
        assert await db.scalar(select(func.count()).select_from(EventoConsumido)) == 1
    assert await importes(base) == antes
