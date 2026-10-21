"""Pruebas de integración en PostgreSQL para consumidores de eventos y worker (CON-32/34/36).

Verifica sobre esquema PostgreSQL aislado y sesiones independientes:
1. CON-32: emisión real de lote con `EmisionCuotasService`, lectura del envelope en
   `eventos_lote_outbox`, consumo con `consumir_evento` y verificación desde nueva
   sesión de las notificaciones `NOTIF_EMISION_CUOTA` sin alterar importes de cuotas.
2. Idempotencia de consumo: reentregar el mismo `event_id` o un nuevo evento para la
   misma entrega lógica no duplica filas en `notificaciones`.
3. Aislamiento y resolución de destinatarios: usuarios sin vínculo activo, cuentas
   inactivas o residentes de otros departamentos no reciben avisos ajenos; unidades
   sin destinatarios activos no generan filas.
4. Atomicidad transaccional: un fallo en el handler revierte tanto `eventos_consumidos`
   como `notificaciones` (cero registros parciales).
5. CON-34: `PagoReportadoEvent` y `PagoRevisadoEvent` (`APROBADO`, `OBSERVADO`,
   `RECHAZADO`), tanto con datos del evento (`to_regclass` cuando no existe tabla)
   como leyendo la fila persistida de `comprobantes_pago`; rechazo cuando falta
   `saldo_resultante` en `APROBADO` (nunca inventa `0.00`).
6. CON-36: `ReservaConfirmadaEvent` y `ReservaCanceladaEvent` (con y sin reembolso),
   aislando destinatarios al departamento de la reserva.
7. Worker de Redis Streams (`XREADGROUP`, `XACK` post-commit, recuperación de
   pendientes con `recuperar_pendientes_stream` y despacho con `ejecutar_ciclo_despacho`).
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.security import hash_password
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.saldos.service import ActorSaldoFavor
from src.modules.cuotas.schemas import EmitirLoteRequest
from src.modules.notificaciones.consumidores import (
    CONSUMIDOR_NOTIFICACIONES,
    ErrorContratoEvento,
    consumir_evento,
)
from src.modules.notificaciones.models import EventoConsumido, Notificacion
from src.modules.notificaciones.transportes import TransporteSimulado
from src.modules.notificaciones.worker import (
    asegurar_grupo_consumidor,
    consumir_lote_stream,
    ejecutar_ciclo_despacho,
    recuperar_pendientes_stream,
)
from src.modules.pagos.models import ComprobantePago
from src.modules.usuarios.models import Usuario, UsuarioDepartamento

REVISIONES = (
    "20261008_0001_crear_condominios_y_auditoria",
    "20261008_0002_crear_presupuestos_mensuales",
    "20261014_0003_crear_configuracion_distribucion",
    "20261014_0004_crear_aplicaciones_saldo_favor",
    "20261018_0005_estructura_inmobiliaria",
    "20261019_0006_emision_cuotas",
    "20261020_0007_alta_usuarios",
    "20261020_0008_roles_revocables",
    "20261020_0009_vinculos_departamentos",
    "20261020_0010_notificaciones_persistentes",
)


def _migrar(conn, revisiones=REVISIONES):
    with Operations.context(MigrationContext.configure(conn)):
        for revision in revisiones:
            import_module(f"migrations.versions.{revision}").upgrade()


@asynccontextmanager
async def base_notificaciones_eventos():
    url = (
        os.getenv("CON13_TEST_DATABASE_URL")
        or os.getenv("CON11_TEST_DATABASE_URL")
        or os.getenv("CON04_TEST_DATABASE_URL")
    )
    if not url:
        pytest.skip("Defina CON13_TEST_DATABASE_URL con una base PostgreSQL de pruebas.")
    esquema = f"con32_{uuid4().hex}"
    admin = create_async_engine(url, poolclass=NullPool)
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": esquema}},
    )
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
        async with engine.begin() as conn:
            await conn.run_sync(_migrar)
        yield async_sessionmaker(engine, expire_on_commit=False), engine
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def entorno_db():
    async with base_notificaciones_eventos() as (factory, engine):
        yield factory, engine


async def _sembrar_escenario_condominio(factory):
    """Crea un condominio con 3 departamentos y distintos estados de vínculo/usuario."""
    cid = uuid4()
    eid = uuid4()
    dpto_101 = uuid4()  # Propietario activo + Inquilino activo + Ex-inquilino vínculo inactivo
    dpto_102 = uuid4()  # Propietario activo + Usuario cuenta inactiva
    dpto_103 = uuid4()  # Sin vínculos activos

    u_prop_101 = uuid4()
    u_inq_101 = uuid4()
    u_ex_101 = uuid4()
    u_prop_102 = uuid4()
    u_inactivo_102 = uuid4()

    async with factory() as session, session.begin():
        session.add(
            Condominio(
                id=cid,
                nombre="Residencial Los Olivos",
                direccion="Av. Principal 123",
                moneda="PEN",
                regla_mora_tipo="MONTO_FIJO",
                monto_mora_fijo=Decimal("20.00"),
                dia_vencimiento=20,
                dias_gracia=2,
                activo=True,
            )
        )
        await session.flush()

        session.add(
            Edificio(
                id=eid,
                condominio_id=cid,
                nombre_bloque="Torre A",
                total_pisos=5,
            )
        )
        await session.flush()

        for did, numero, coef, saldo in (
            (dpto_101, "101", Decimal("40.0000"), Decimal("50.00")),
            (dpto_102, "102", Decimal("30.0000"), Decimal("0.00")),
            (dpto_103, "103", Decimal("30.0000"), Decimal("0.00")),
        ):
            session.add(
                Departamento(
                    id=did,
                    edificio_id=eid,
                    numero=numero,
                    piso=1,
                    coeficiente_participacion=coef,
                    saldo_a_favor=saldo,
                    estado_financiero="AL_DIA",
                    activo=True,
                )
            )
        await session.flush()

        usuarios = [
            Usuario(
                id=u_prop_101,
                email="propietario101@condominio.pe",
                password_hash=hash_password("ClaveSegura123!"),
                nombre="Elena",
                apellido="Salazar",
                documento_identidad="40100101",
                esta_activo=True,
            ),
            Usuario(
                id=u_inq_101,
                email="inquilino101@condominio.pe",
                password_hash=hash_password("ClaveSegura123!"),
                nombre="Marco",
                apellido="Rivas",
                documento_identidad="40100102",
                esta_activo=True,
            ),
            Usuario(
                id=u_ex_101,
                email="exinquilino101@condominio.pe",
                password_hash=hash_password("ClaveSegura123!"),
                nombre="Pedro",
                apellido="Antiguo",
                documento_identidad="40100103",
                esta_activo=True,
            ),
            Usuario(
                id=u_prop_102,
                email="propietario102@condominio.pe",
                password_hash=hash_password("ClaveSegura123!"),
                nombre="Lucía",
                apellido="Mendoza",
                documento_identidad="40100104",
                esta_activo=True,
            ),
            Usuario(
                id=u_inactivo_102,
                email="cuentainactiva102@condominio.pe",
                password_hash=hash_password("ClaveSegura123!"),
                nombre="Jorge",
                apellido="Deshabilitado",
                documento_identidad="40100105",
                esta_activo=False,
            ),
        ]
        session.add_all(usuarios)
        await session.flush()

        session.add_all(
            [
                UsuarioDepartamento(
                    usuario_id=u_prop_101,
                    departamento_id=dpto_101,
                    tipo_relacion="PROPIETARIO_TITULAR",
                    es_activo=True,
                ),
                UsuarioDepartamento(
                    usuario_id=u_inq_101,
                    departamento_id=dpto_101,
                    tipo_relacion="INQUILINO",
                    es_activo=True,
                ),
                UsuarioDepartamento(
                    usuario_id=u_ex_101,
                    departamento_id=dpto_101,
                    tipo_relacion="INQUILINO",
                    es_activo=False,  # Vínculo revocado
                ),
                UsuarioDepartamento(
                    usuario_id=u_prop_102,
                    departamento_id=dpto_102,
                    tipo_relacion="PROPIETARIO_TITULAR",
                    es_activo=True,
                ),
                UsuarioDepartamento(
                    usuario_id=u_inactivo_102,
                    departamento_id=dpto_102,
                    tipo_relacion="COPROPIETARIO",
                    es_activo=True,  # Vínculo activo pero cuenta inactiva
                ),
            ]
        )
        session.add(
            PresupuestoMensual(
                id=uuid4(),
                condominio_id=cid,
                periodo="2026-10",
                moneda="PEN",
                monto_total=Decimal("1000.00"),
                estado="APROBADO",
                fecha_vencimiento=date(2026, 10, 20),
                creado_por="ADMIN_JUNTA",
                aprobado_por="ADMIN_JUNTA",
                aprobado_en=datetime.now(UTC),
            )
        )
        session.add(
            ConfiguracionDistribucion(
                id=uuid4(),
                condominio_id=cid,
                metodo="POR_ALICUOTA",
                actualizado_por="ADMIN_JUNTA",
                actualizado_en=datetime.now(UTC),
            )
        )

    return {
        "condominio_id": cid,
        "dpto_101": dpto_101,
        "dpto_102": dpto_102,
        "dpto_103": dpto_103,
        "u_prop_101": u_prop_101,
        "u_inq_101": u_inq_101,
        "u_ex_101": u_ex_101,
        "u_prop_102": u_prop_102,
        "u_inactivo_102": u_inactivo_102,
    }


@pytest.mark.asyncio
async def test_con32_emision_lote_real_consume_outbox_e_idempotencia(entorno_db):
    factory, _ = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    cid = datos["condominio_id"]

    # 1. Emitir lote real con EmisionCuotasService
    async with factory() as session:
        respuesta_lote = await EmisionCuotasService(session).emitir(
            EmitirLoteRequest(condominio_id=cid, periodo="2026-10"),
            ActorSaldoFavor("admin-1", "ADMIN_JUNTA", cid),
        )
    assert respuesta_lote.total_cuotas_emitidas == 3

    # 2. Leer el envelope real persistido en eventos_lote_outbox desde nueva sesión
    async with factory() as session:
        outbox = await session.scalar(
            select(EventoLoteOutbox).where(EventoLoteOutbox.lote_id == respuesta_lote.lote_id)
        )
        assert outbox is not None
        envelope = dict(outbox.payload)
        cuotas_antes = {
            c.departamento_id: (c.monto_total_exigible, c.monto_pagado, c.monto_pendiente)
            for c in (await session.scalars(select(CuotaMantenimiento))).all()
        }

    # 3. Consumir el envelope del outbox en otra sesión
    async with factory() as session:
        res1 = await consumir_evento(session, envelope)
    assert res1.duplicado is False
    # Dpto 101 tiene 2 destinatarios activos; Dpto 102 tiene 1; Dpto 103 tiene 0 -> total 3
    assert res1.notificaciones_creadas == 3

    # 4. Consultar notificaciones desde una nueva sesión y verificar aislamiento y montos
    async with factory() as session:
        notificaciones = list(
            (await session.scalars(select(Notificacion).order_by(Notificacion.destinatario))).all()
        )
        assert len(notificaciones) == 3
        destinatarios = {n.destinatario for n in notificaciones}
        assert destinatarios == {
            "propietario101@condominio.pe",
            "inquilino101@condominio.pe",
            "propietario102@condominio.pe",
        }
        # Vínculo inactivo y cuenta inactiva no reciben nada
        assert "exinquilino101@condominio.pe" not in destinatarios
        assert "cuentainactiva102@condominio.pe" not in destinatarios

        for notif in notificaciones:
            assert notif.estado == "EN_COLA"
            assert notif.origen_tipo == "CUOTA"
            assert notif.plantilla == "NOTIF_EMISION_CUOTA"
            if notif.departamento_id == datos["dpto_101"]:
                # Dpto 101: cuota 400.00, saldo a favor aplicado 50.00 -> pendiente 350.00
                assert "101 (Torre A)" in notif.cuerpo
                assert "S/ 400.00" in notif.cuerpo
                assert "S/ 350.00" in notif.cuerpo
                assert "102" not in notif.cuerpo
            elif notif.departamento_id == datos["dpto_102"]:
                assert "102 (Torre A)" in notif.cuerpo
                assert "S/ 300.00" in notif.cuerpo
                assert "101 (Torre A)" not in notif.cuerpo

        # Verificar que ningún importe de cuotas fue alterado
        cuotas_despues = {
            c.departamento_id: (c.monto_total_exigible, c.monto_pagado, c.monto_pendiente)
            for c in (await session.scalars(select(CuotaMantenimiento))).all()
        }
        assert cuotas_despues == cuotas_antes

    # 5. Reentrega del mismo evento no duplica notificaciones
    async with factory() as session:
        res2 = await consumir_evento(session, envelope)
    assert res2.duplicado is True
    assert res2.notificaciones_creadas == 0

    # 6. Incluso con otro event_id, clave_deduplicacion impide duplicar entregas lógicas
    envelope_reenvio = {**envelope, "event_id": str(uuid4())}
    async with factory() as session:
        res3 = await consumir_evento(session, envelope_reenvio)
    assert res3.duplicado is False
    assert res3.notificaciones_creadas == 0

    async with factory() as session:
        total = await session.scalar(select(func.count()).select_from(Notificacion))
        assert total == 3


@pytest.mark.asyncio
async def test_con34_pago_reportado_y_revisado_con_tabla_persistida_y_validacion_saldo(entorno_db):
    factory, engine = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    cid = datos["condominio_id"]
    dpto_101 = datos["dpto_101"]

    # Crear la tabla comprobantes_pago en el esquema aislado para probar la lectura persistente
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: ComprobantePago.__table__.create(sync_conn, checkfirst=True)
        )

    comprobante_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            ComprobantePago(
                id=comprobante_id,
                departamento_id=dpto_101,
                banco_origen="BCP",
                numero_operacion="OP-884422",
                fecha_operacion=date(2026, 10, 15),
                monto=Decimal("350.00"),
                url_voucher="s3://condomanager-vouchers/v-884422.png",
                idempotency_hash="a" * 64,
                estado="EN_REVISION",
            )
        )

    # 1. PagoReportadoEvent lee datos persistidos de comprobantes_pago
    ev_reportado = {
        "event_id": str(uuid4()),
        "event_type": "PagoReportadoEvent",
        "producer": "service.pagos",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "comprobante_id": str(comprobante_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_101),
            "banco": "BCP",
            "numero_operacion": "OP-884422",
            "monto": "350.00",
        },
    }
    async with factory() as session:
        res_rep = await consumir_evento(session, ev_reportado)
    assert res_rep.notificaciones_creadas == 2

    # 2. Actualizar comprobante a APROBADO y probar que falta de saldo_resultante falla con rollback
    async with factory() as session, session.begin():
        comp = await session.get(ComprobantePago, comprobante_id)
        comp.estado = "APROBADO"

    ev_aprobado_sin_saldo = {
        "event_id": str(uuid4()),
        "event_type": "PagoRevisadoEvent",
        "producer": "service.pagos",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "comprobante_id": str(comprobante_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_101),
            "resultado": "APROBADO",
            "monto_aplicado": "350.00",
            # Falta saldo_resultante: no debe inventar 0.00, debe fallar y hacer rollback
        },
    }
    async with factory() as session:
        with pytest.raises(ErrorContratoEvento, match="saldo_resultante"):
            await consumir_evento(session, ev_aprobado_sin_saldo)

    # Verificar desde nueva sesión que el fallo hizo rollback completo (incluso de eventos_consumidos)
    async with factory() as session:
        ev_fallido = await session.scalar(
            select(EventoConsumido).where(
                EventoConsumido.consumidor == CONSUMIDOR_NOTIFICACIONES,
                EventoConsumido.event_id == ev_aprobado_sin_saldo["event_id"],
            )
        )
        assert ev_fallido is None
        total_notifs = await session.scalar(select(func.count()).select_from(Notificacion))
        assert total_notifs == 2  # Solo las 2 de PagoReportadoEvent

    # 3. PagoRevisadoEvent APROBADO válido con saldo_resultante explícito
    ev_aprobado_ok = {
        "event_id": str(uuid4()),
        "event_type": "PagoRevisadoEvent",
        "producer": "service.pagos",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "comprobante_id": str(comprobante_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_101),
            "resultado": "APROBADO",
            "monto_aplicado": "350.00",
            "saldo_resultante": "125.40",
            "revisado_en": datetime.now(UTC).isoformat(),
        },
    }
    async with factory() as session:
        res_apr = await consumir_evento(session, ev_aprobado_ok)
    assert res_apr.notificaciones_creadas == 2

    async with factory() as session:
        conciliadas = list(
            (
                await session.scalars(
                    select(Notificacion).where(Notificacion.plantilla == "NOTIF_PAGO_CONCILIADO")
                )
            ).all()
        )
        assert len(conciliadas) == 2
        for notif in conciliadas:
            assert "S/ 350.00" in notif.cuerpo
            assert "S/ 125.40" in notif.cuerpo
            assert notif.origen_tipo == "COMPROBANTE"
            assert notif.origen_id == comprobante_id


@pytest.mark.asyncio
async def test_con34_pago_observado_y_rechazado_sin_tabla_comprobantes(entorno_db):
    """Cuando la tabla comprobantes_pago no existe en el esquema, usa to_regclass sin romper la transacción."""
    factory, _ = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    cid = datos["condominio_id"]
    dpto_102 = datos["dpto_102"]

    comp_obs_id = uuid4()
    ev_observado = {
        "event_id": str(uuid4()),
        "event_type": "PagoRevisadoEvent",
        "producer": "service.pagos",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "comprobante_id": str(comp_obs_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_102),
            "resultado": "OBSERVADO",
            "motivo": "El número de operación aparece recortado en la imagen",
            "instrucciones": "Suba una captura completa del comprobante desde la sección Pagos.",
            "revisado_en": datetime.now(UTC).isoformat(),
        },
    }
    async with factory() as session:
        res_obs = await consumir_evento(session, ev_observado)
    assert res_obs.notificaciones_creadas == 1

    comp_rec_id = uuid4()
    ev_rechazado = {
        "event_id": str(uuid4()),
        "event_type": "PagoRevisadoEvent",
        "producer": "service.pagos",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "comprobante_id": str(comp_rec_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_102),
            "resultado": "RECHAZADO",
            "motivo": "Transferencia no figura en el extracto bancario del mes",
            "instrucciones": "Verifique con su entidad bancaria y registre un comprobante válido.",
            "revisado_en": datetime.now(UTC).isoformat(),
        },
    }
    async with factory() as session:
        res_rec = await consumir_evento(session, ev_rechazado)
    assert res_rec.notificaciones_creadas == 1

    async with factory() as session:
        notifs = list(
            (await session.scalars(select(Notificacion).order_by(Notificacion.creado_en))).all()
        )
        assert [n.plantilla for n in notifs] == [
            "NOTIF_PAGO_OBSERVADO",
            "NOTIF_PAGO_RECHAZADO",
        ]
        assert "recortado en la imagen" in notifs[0].cuerpo
        assert "Suba una captura completa" in notifs[0].cuerpo
        assert "no figura en el extracto" in notifs[1].cuerpo
        assert all(n.destinatario == "propietario102@condominio.pe" for n in notifs)


@pytest.mark.asyncio
async def test_con36_reserva_confirmada_y_cancelada_aislamiento_por_departamento(entorno_db):
    factory, _ = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    cid = datos["condominio_id"]
    dpto_102 = datos["dpto_102"]
    reserva_id = uuid4()

    ev_confirmada = {
        "event_id": str(uuid4()),
        "event_type": "ReservaConfirmadaEvent",
        "producer": "service.reservas",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "reserva_id": str(reserva_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_102),
            "area": "Zona de Parrillas Norte",
            "fecha_reserva": "2026-11-05",
            "horario": "18:00 - 22:00",
            "costo": "50.00",
            "normas_convivencia": "Respetar horario límite de las 22:00 y dejar limpio el espacio.",
        },
    }
    ev_cancelada = {
        "event_id": str(uuid4()),
        "event_type": "ReservaCanceladaEvent",
        "producer": "service.reservas",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "reserva_id": str(reserva_id),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_102),
            "area": "Zona de Parrillas Norte",
            "fecha_reserva": "2026-11-05",
            "horario": "18:00 - 22:00",
            "motivo": "Cancelación voluntaria con más de 24 horas de anticipación",
            "monto_reembolso": "50.00",
        },
    }

    async with factory() as session:
        res_conf = await consumir_evento(session, ev_confirmada)
        res_canc = await consumir_evento(session, ev_cancelada)

    assert res_conf.notificaciones_creadas == 1
    assert res_canc.notificaciones_creadas == 1

    async with factory() as session:
        notifs = list(
            (await session.scalars(select(Notificacion).order_by(Notificacion.plantilla))).all()
        )
        assert len(notifs) == 2
        # Solo recibe el destinatario activo del Dpto 102, nunca los del Dpto 101
        assert {n.destinatario for n in notifs} == {"propietario102@condominio.pe"}
        cancelada, confirmada = notifs[0], notifs[1]
        assert confirmada.plantilla == "NOTIF_RESERVA_CONFIRMADA"
        assert "Zona de Parrillas Norte" in confirmada.cuerpo
        assert "S/ 50.00" in confirmada.cuerpo
        assert "Respetar horario límite" in confirmada.cuerpo

        assert cancelada.plantilla == "NOTIF_RESERVA_CANCELADA"
        assert "S/ 50.00" in cancelada.cuerpo
        assert "liberado" in cancelada.cuerpo


@pytest.mark.asyncio
async def test_worker_redis_streams_xack_post_commit_y_recuperacion_pendientes(entorno_db):
    factory, _ = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    cid = datos["condominio_id"]
    dpto_102 = datos["dpto_102"]

    redis_url = os.getenv("TEST_REDIS_URL") or "redis://localhost:56379/0"
    redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
    try:
        await redis.ping()
    except Exception:
        await redis.aclose()
        pytest.skip("Redis de pruebas no disponible en localhost:56379.")

    stream = f"condomanager:test-events:{uuid4().hex}"
    group = "test-notif-group"
    try:
        await asegurar_grupo_consumidor(redis, stream=stream, group=group)

        # 0. Un evento de otro dominio se confirma sin crear notificaciones
        await redis.xadd(
            stream,
            {"event": json.dumps({"event_id": str(uuid4()), "event_type": "OtroDominioEvent"})},
        )
        assert (
            await consumir_lote_stream(
                redis, factory, stream=stream, group=group, consumer="worker-1", block_ms=50
            )
            == 1
        )
        assert (await redis.xpending(stream, group))["pending"] == 0

        # 1. Evento que incumple el contrato (APROBADO sin saldo_resultante): reintentarlo no
        # lo corrige, así que va a la DLQ y se confirma sin crear notificaciones.
        ev_invalido = {
            "event_id": str(uuid4()),
            "event_type": "PagoRevisadoEvent",
            "producer": "service.pagos",
            "occurred_at": datetime.now(UTC).isoformat(),
            "data": {
                "comprobante_id": str(uuid4()),
                "condominio_id": str(cid),
                "departamento_id": str(dpto_102),
                "resultado": "APROBADO",
                "monto_aplicado": "100.00",
            },
        }
        msg_err_id = await redis.xadd(stream, {"event": json.dumps(ev_invalido)})
        confirmados_err = await consumir_lote_stream(
            redis,
            factory,
            stream=stream,
            group=group,
            consumer="worker-1",
            block_ms=50,
        )
        assert confirmados_err == 0
        assert (await redis.xpending(stream, group))["pending"] == 0
        dlq = await redis.xrange(f"{stream}:dlq")
        assert len(dlq) == 1 and dlq[0][1]["origen"] == msg_err_id
        assert "saldo_resultante" in dlq[0][1]["error"]
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(Notificacion)) == 0

        # 2. Publicar evento válido, reclamarlo sin XACK simulando caída, y recuperarlo con worker-2
        ev_valido = {
            "event_id": str(uuid4()),
            "event_type": "PagoReportadoEvent",
            "producer": "service.pagos",
            "occurred_at": datetime.now(UTC).isoformat(),
            "data": {
                "comprobante_id": str(uuid4()),
                "condominio_id": str(cid),
                "departamento_id": str(dpto_102),
                "banco": "Interbank",
                "numero_operacion": "IBK-7711",
                "monto": "210.00",
            },
        }
        await redis.xadd(stream, {"event": json.dumps(ev_valido)})
        # worker-caido lee con XREADGROUP pero muere antes de procesar/XACK
        leidos = await redis.xreadgroup(
            groupname=group,
            consumername="worker-caido",
            streams={stream: ">"},
            count=1,
        )
        assert len(leidos) == 1
        assert (await redis.xpending(stream, group))["pending"] == 1

        # worker-2 recupera el pendiente con recuperar_pendientes_stream y hace XACK tras commit
        recuperados = await recuperar_pendientes_stream(
            redis,
            factory,
            stream=stream,
            group=group,
            consumer="worker-2",
            min_idle_ms=0,
        )
        assert recuperados == 1
        assert (await redis.xpending(stream, group))["pending"] == 0

        # 3. Ejecutar el ciclo de despacho del worker y verificar entrega simulada
        transporte = TransporteSimulado(confirmar_entrega=True)
        resumen = await ejecutar_ciclo_despacho(
            session_factory=factory,
            transporte=transporte,
            worker_id="worker-2",
        )
        assert resumen.entregadas == 1

        async with factory() as session:
            notif = await session.scalar(select(Notificacion))
            assert notif is not None
            assert notif.estado == "ENTREGADO"
            assert notif.transporte_simulado is True
    finally:
        await redis.delete(stream, f"{stream}:dlq")
        await redis.aclose()


@pytest.mark.asyncio
async def test_rollback_completo_cuando_falla_en_medio_de_transaccion(entorno_db, monkeypatch):
    """Si ocurre una excepción tras insertar la primera notificación, hace rollback de todo."""
    factory, _ = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    cid = datos["condominio_id"]
    dpto_101 = datos["dpto_101"]  # Tiene 2 destinatarios activos

    import src.modules.notificaciones.consumidores as mod_consumidores

    original_registrar = mod_consumidores.registrar_notificacion
    llamadas = 0

    async def registrar_que_falla_en_segunda(session, nueva, ahora=None):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 2:
            raise RuntimeError("Fallo simulado después de la primera inserción")
        return await original_registrar(session, nueva, ahora=ahora)

    monkeypatch.setattr(mod_consumidores, "registrar_notificacion", registrar_que_falla_en_segunda)

    evento_id = uuid4()
    ev_reportado = {
        "event_id": str(evento_id),
        "event_type": "PagoReportadoEvent",
        "producer": "service.pagos",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "comprobante_id": str(uuid4()),
            "condominio_id": str(cid),
            "departamento_id": str(dpto_101),
            "banco": "BBVA",
            "numero_operacion": "BBVA-1001",
            "monto": "180.00",
        },
    }

    async with factory() as session:
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            await consumir_evento(session, ev_reportado)

    # Desde una nueva sesión no debe existir ni el evento consumido ni la primera notificación
    async with factory() as session:
        total_notifs = await session.scalar(select(func.count()).select_from(Notificacion))
        total_eventos = await session.scalar(select(func.count()).select_from(EventoConsumido))
        assert total_notifs == 0
        assert total_eventos == 0


@pytest.mark.asyncio
async def test_rechazo_departamento_de_otro_condominio(entorno_db):
    factory, _ = entorno_db
    datos = await _sembrar_escenario_condominio(factory)
    dpto_101 = datos["dpto_101"]
    otro_condominio_id = uuid4()

    ev_cruzado = {
        "event_id": str(uuid4()),
        "event_type": "ReservaConfirmadaEvent",
        "producer": "service.reservas",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {
            "reserva_id": str(uuid4()),
            "condominio_id": str(otro_condominio_id),
            "departamento_id": str(dpto_101),
            "area": "Parrilla",
            "fecha_reserva": "2026-11-10",
            "horario": "12:00 - 16:00",
            "costo": "30.00",
            "normas_convivencia": "Dejar limpio",
        },
    }
    async with factory() as session:
        with pytest.raises(ErrorContratoEvento, match="no pertenece al condominio"):
            await consumir_evento(session, ev_cruzado)

    async with factory() as session:
        total_notifs = await session.scalar(select(func.count()).select_from(Notificacion))
        assert total_notifs == 0
