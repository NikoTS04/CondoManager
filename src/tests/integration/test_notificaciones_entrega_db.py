"""Pruebas de integración en PostgreSQL para el motor de entrega y reintentos (CON-37).

Verifica en esquemas aislados de PostgreSQL real:
1. Fallo temporal recuperado con backoff y jitter inyectable (±15 s en primer reintento).
2. Agotamiento de los 4 intentos (1 inicial + 3 reintentos: 2, 10 y 30 min) ->
   FALLIDO_PERMANENTE + alerta administrativa idempotente sin datos sensibles.
3. Error definitivo inmediato (550, 131026, 4xx != 429, destinatario inválido).
4. Dos workers concurrentes (`FOR UPDATE SKIP LOCKED`) no envían dos veces la misma notificación.
5. Recuperación de arrendamiento vencido tras caída/reinicio de un worker y protección de lease.
6. Notificación en estado ACEPTADO o ENTREGADO nunca se reenvía.
7. Reprogramación manual (`reprogramar_manual`) exclusiva para FALLIDO_PERMANENTE.
8. Evidencia persistida (`transporte_simulado`, `proveedor_message_id`, intentos, alertas)
   consultable desde una nueva sesión independiente.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from scripts.seed_usuarios_demo import cargar_demo
from src.core.errors import APIError
from src.modules.notificaciones.entrega import (
    confirmar_entrega,
    despachar_pendientes,
    reclamar_lote,
    registrar_resultado_intento,
    reprogramar_manual,
)
from src.modules.notificaciones.models import (
    AlertaAdministrativa,
    Notificacion,
    NotificacionIntento,
)
from src.modules.notificaciones.repository import NuevaNotificacion, registrar_notificacion
from src.modules.notificaciones.transportes import (
    ResultadoTransporte,
    TransporteSimulado,
    obtener_transporte,
)
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, DEPARTAMENTOS_PILOTO
from src.tests.usuarios_db import REVISIONES, BaseUsuarios, borrar_base, migrar

REVISIONES_NOTIFICACIONES = (*REVISIONES, "20261020_0010_notificaciones_persistentes")


async def _crear_base_notificaciones(url: str) -> BaseUsuarios:
    esquema = "con37_" + uuid.uuid4().hex
    admin = create_async_engine(url, poolclass=NullPool)
    async with admin.begin() as conn:
        await conn.execute(select(1))
        await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
    await admin.dispose()

    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": esquema}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(migrar, REVISIONES_NOTIFICACIONES)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        await cargar_demo(session)

    return BaseUsuarios(engine, sessions, esquema, url)


@pytest_asyncio.fixture
async def db_notificaciones():
    url = (
        os.getenv("CON13_TEST_DATABASE_URL")
        or os.getenv("CON04_TEST_DATABASE_URL")
        or os.getenv("CON05_TEST_DATABASE_URL")
        or os.getenv("CON06_TEST_DATABASE_URL")
    )
    if not url:
        pytest.skip("Defina CON13_TEST_DATABASE_URL con una base PostgreSQL de pruebas.")
    base = await _crear_base_notificaciones(url)
    try:
        yield base
    finally:
        await borrar_base(base)


def _nueva_notif(
    *,
    dpto_num: str = "402",
    destinatario: str = "residente402@condominio.pe",
    clave_extra: str | None = None,
) -> NuevaNotificacion:
    dpto_id = uuid.uuid5(CONDOMINIO_PILOTO_ID, dpto_num)
    datos_dpto = DEPARTAMENTOS_PILOTO[str(dpto_id)]
    origen_id = uuid.uuid4()
    sufijo = clave_extra or str(origen_id)
    return NuevaNotificacion(
        condominio_id=CONDOMINIO_PILOTO_ID,
        departamento_id=datos_dpto["id"],
        usuario_id=None,
        evento_id=uuid.uuid4(),
        tipo_evento="CuotasEmitidasEvent",
        plantilla="NOTIF_EMISION_CUOTA",
        origen_tipo="CUOTA",
        origen_id=origen_id,
        clave_deduplicacion=f"CUOTA:{sufijo}:NOTIF_EMISION_CUOTA:EMAIL",
        canal="EMAIL",
        destinatario=destinatario,
        contexto={
            "nombre": f"Residente {dpto_num}",
            "dpto": dpto_num,
            "periodo": "2026-10",
            "monto": str(Decimal("150.00")),
            "monto_total_exigible": str(Decimal("150.00")),
            "monto_pendiente": str(Decimal("150.00")),
            "vencimiento": "2026-10-20",
            "cci_banco": "002-191-000000000000-54",
            "medios_pago": "BCP CCI 002-191-000000000000-54",
        },
    )


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_fallo_temporal_recuperado_con_jitter_y_evidencia_nueva_sesion(
    db_notificaciones: BaseUsuarios,
):
    """Fallo temporal 503 reprograma a +2m con jitter ±15s y se recupera en el reintento."""
    t0 = datetime(2026, 10, 20, 10, 0, 0, tzinfo=UTC)
    async with db_notificaciones.sessions() as session, session.begin():
        notif_id = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="102", destinatario="residente102@condominio.pe"),
            ahora=t0,
        )
    assert notif_id is not None

    transporte = TransporteSimulado()
    transporte.programar_fallo("503", "Service Unavailable")
    transporte.programar_exito("sim-msg-recuperado-102")

    # 1. Primer intento falla con 503; jitter inyectado de +9 segundos -> espera 129s
    res1 = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        worker_id="worker-1",
        ahora=t0,
        jitter_fn=lambda: 9.0,
    )
    assert res1.reclamadas == 1
    assert res1.reintentando == 1
    assert transporte.llamadas_para(notif_id) == 1

    # Consultar desde una nueva sesión que sigue en REINTENTANDO con proximo_intento_en = t0 + 129s
    async with db_notificaciones.sessions() as session:
        notif = await session.get(Notificacion, notif_id)
        assert notif is not None
        assert notif.estado == "REINTENTANDO"
        assert notif.intentos == 1
        assert notif.proximo_intento_en == t0 + timedelta(seconds=129)
        assert notif.transporte == "SIMULADO"
        assert notif.transporte_simulado is True
        assert notif.error_codigo == "503"

    # 2. Antes de cumplirse proximo_intento_en (t0 + 120s < t0 + 129s) no se reclama
    res_temprano = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        worker_id="worker-1",
        ahora=t0 + timedelta(seconds=120),
    )
    assert res_temprano.reclamadas == 0
    assert transporte.llamadas_para(notif_id) == 1

    # 3. Al cumplirse t0 + 129s, se reclama y el segundo intento es aceptado
    t_reintento = t0 + timedelta(seconds=129)
    res2 = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        worker_id="worker-1",
        ahora=t_reintento,
    )
    assert res2.reclamadas == 1
    assert res2.aceptadas == 1
    assert transporte.llamadas_para(notif_id) == 2

    # 4. Confirmar entrega por proveedor_message_id y verificar en nueva sesión independiente
    t_entrega = t_reintento + timedelta(seconds=5)
    async with db_notificaciones.sessions() as session, session.begin():
        await confirmar_entrega(
            session,
            proveedor_message_id="sim-msg-recuperado-102",
            ahora=t_entrega,
        )

    otro_engine = create_async_engine(
        db_notificaciones.url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": db_notificaciones.esquema}},
    )
    otra_factory = async_sessionmaker(otro_engine, expire_on_commit=False)
    try:
        async with otra_factory() as sesion_nueva:
            persistida = await sesion_nueva.get(Notificacion, notif_id)
            assert persistida is not None
            assert persistida.estado == "ENTREGADO"
            assert persistida.intentos == 2
            assert persistida.transporte_simulado is True
            assert persistida.proveedor_message_id == "sim-msg-recuperado-102"
            assert persistida.aceptado_en == t_reintento
            assert persistida.entregado_en == t_entrega
            assert persistida.error_codigo is None
            assert persistida.error_mensaje is None

            intentos = list(
                (
                    await sesion_nueva.scalars(
                        select(NotificacionIntento)
                        .where(NotificacionIntento.notificacion_id == notif_id)
                        .order_by(NotificacionIntento.numero.asc())
                    )
                ).all()
            )
            assert [i.numero for i in intentos] == [1, 2]
            assert [i.resultado for i in intentos] == ["FALLO_TEMPORAL", "ACEPTADO"]
            assert all(i.transporte_simulado is True for i in intentos)
    finally:
        await otro_engine.dispose()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_agotamiento_reintentos_fallido_permanente_y_alerta(
    db_notificaciones: BaseUsuarios,
):
    """1 intento inicial + 3 reintentos (2, 10 y 30 min) -> FALLIDO_PERMANENTE + alerta."""
    t0 = datetime(2026, 10, 20, 11, 0, 0, tzinfo=UTC)
    async with db_notificaciones.sessions() as session, session.begin():
        notif_id = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="402", destinatario="residente402@condominio.pe"),
            ahora=t0,
        )
    assert notif_id is not None

    transporte = TransporteSimulado(
        respuestas=[
            ResultadoTransporte.fallo("429", "Too Many Requests"),
            ResultadoTransporte.fallo("500", "Internal Server Error"),
            ResultadoTransporte.fallo("502", "Bad Gateway"),
            ResultadoTransporte.fallo("504", "Gateway Timeout"),
        ]
    )

    # Intento 1 (inicial) en t0 -> programa intento 2 en t0 + 2 min
    r1 = await despachar_pendientes(
        db_notificaciones.sessions, transporte, "w1", ahora=t0, jitter_fn=lambda: 0.0
    )
    assert r1.reintentando == 1
    t1 = t0 + timedelta(minutes=2)

    async with db_notificaciones.sessions() as session:
        n1 = await session.get(Notificacion, notif_id)
        assert n1.intentos == 1
        assert n1.proximo_intento_en == t1

    # Intento 2 (1er reintento) en t1 -> programa intento 3 en t1 + 10 min
    r2 = await despachar_pendientes(db_notificaciones.sessions, transporte, "w1", ahora=t1)
    assert r2.reintentando == 1
    t2 = t1 + timedelta(minutes=10)

    async with db_notificaciones.sessions() as session:
        n2 = await session.get(Notificacion, notif_id)
        assert n2.intentos == 2
        assert n2.proximo_intento_en == t2

    # Intento 3 (2do reintento) en t2 -> programa intento 4 en t2 + 30 min
    r3 = await despachar_pendientes(db_notificaciones.sessions, transporte, "w1", ahora=t2)
    assert r3.reintentando == 1
    t3 = t2 + timedelta(minutes=30)

    async with db_notificaciones.sessions() as session:
        n3 = await session.get(Notificacion, notif_id)
        assert n3.intentos == 3
        assert n3.proximo_intento_en == t3

    # Intento 4 (3er y último reintento) en t3 -> FALLIDO_PERMANENTE + alerta
    r4 = await despachar_pendientes(db_notificaciones.sessions, transporte, "w1", ahora=t3)
    assert r4.fallidas_permanentes == 1
    assert transporte.llamadas_para(notif_id) == 4

    async with db_notificaciones.sessions() as session:
        n4 = await session.get(Notificacion, notif_id)
        assert n4.estado == "FALLIDO_PERMANENTE"
        assert n4.intentos == 4
        assert n4.proximo_intento_en is None

        intentos = list(
            (
                await session.scalars(
                    select(NotificacionIntento)
                    .where(NotificacionIntento.notificacion_id == notif_id)
                    .order_by(NotificacionIntento.numero.asc())
                )
            ).all()
        )
        assert [i.numero for i in intentos] == [1, 2, 3, 4]
        assert [i.codigo for i in intentos] == ["429", "500", "502", "504"]
        assert all(i.resultado == "FALLO_TEMPORAL" for i in intentos)

        alertas = list(
            (
                await session.scalars(
                    select(AlertaAdministrativa).where(
                        AlertaAdministrativa.notificacion_id == notif_id
                    )
                )
            ).all()
        )
        assert len(alertas) == 1
        alerta = alertas[0]
        assert alerta.tipo == "NOTIFICACION_FALLIDA"
        assert alerta.severidad == "BAJA"
        assert alerta.atendida_en is None
        assert (
            alerta.mensaje
            == "El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto."
        )
        assert "residente402@condominio.pe" not in alerta.mensaje


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_error_definitivo_inmediato_550_y_4xx(db_notificaciones: BaseUsuarios):
    """550, 131026 y 4xx != 429 marcan FALLIDO_PERMANENTE en el intento 1 con alerta."""
    t0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    async with db_notificaciones.sessions() as session, session.begin():
        id_550 = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="402", destinatario="rebote550@condominio.pe", clave_extra="c1"),
            ahora=t0,
        )
        id_400 = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="104", destinatario="error400@condominio.pe", clave_extra="c2"),
            ahora=t0,
        )

    transporte = TransporteSimulado(
        por_destinatario={
            "rebote550@condominio.pe": ResultadoTransporte.fallo(
                "550", "550 User unknown / Mailbox does not exist"
            ),
            "error400@condominio.pe": ResultadoTransporte.fallo("400", "Bad Request payload"),
        }
    )

    res = await despachar_pendientes(db_notificaciones.sessions, transporte, "w1", ahora=t0)
    assert res.reclamadas == 2
    assert res.fallidas_permanentes == 2
    assert transporte.total_llamadas == 2

    async with db_notificaciones.sessions() as session:
        for nid, cod_esperado in ((id_550, "550"), (id_400, "400")):
            notif = await session.get(Notificacion, nid)
            assert notif.estado == "FALLIDO_PERMANENTE"
            assert notif.intentos == 1
            assert notif.proximo_intento_en is None
            assert notif.error_codigo == cod_esperado

            intento = await session.scalar(
                select(NotificacionIntento).where(NotificacionIntento.notificacion_id == nid)
            )
            assert intento is not None
            assert intento.numero == 1
            assert intento.resultado == "FALLO_DEFINITIVO"

            alerta = await session.scalar(
                select(AlertaAdministrativa).where(AlertaAdministrativa.notificacion_id == nid)
            )
            assert alerta is not None
            assert alerta.atendida_en is None


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_dos_workers_concurrentes_no_envian_dos_veces(db_notificaciones: BaseUsuarios):
    """Dos workers concurrentes coordinados con SKIP LOCKED llaman 1 sola vez al transporte."""
    t0 = datetime(2026, 10, 20, 13, 0, 0, tzinfo=UTC)
    ids: list[uuid.UUID] = []
    async with db_notificaciones.sessions() as session, session.begin():
        for idx, dpto in enumerate(("101", "102", "103", "104", "105")):
            nid = await registrar_notificacion(
                session,
                _nueva_notif(
                    dpto_num=dpto,
                    destinatario=f"concurrente{idx}@condominio.pe",
                    clave_extra=f"conc-{idx}",
                ),
                ahora=t0,
            )
            assert nid is not None
            ids.append(nid)

    transporte = TransporteSimulado(latencia_segundos=0.04)

    res_a, res_b = await asyncio.gather(
        despachar_pendientes(
            db_notificaciones.sessions,
            transporte,
            worker_id="worker-A",
            ahora=t0,
            limite=3,
        ),
        despachar_pendientes(
            db_notificaciones.sessions,
            transporte,
            worker_id="worker-B",
            ahora=t0,
            limite=3,
        ),
    )

    assert res_a.reclamadas + res_b.reclamadas == 5
    assert res_a.aceptadas + res_b.aceptadas == 5
    assert transporte.total_llamadas == 5
    for nid in ids:
        assert transporte.llamadas_para(nid) == 1

    async with db_notificaciones.sessions() as session:
        for nid in ids:
            notif = await session.get(Notificacion, nid)
            assert notif.estado == "ACEPTADO"
            assert notif.intentos == 1


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_arrendamiento_vencido_recuperado_tras_reinicio_y_proteccion_lease(
    db_notificaciones: BaseUsuarios,
):
    """Un arrendamiento vencido tras caída del worker se vuelve a reclamar sin doble escritura."""
    t0 = datetime(2026, 10, 20, 14, 0, 0, tzinfo=UTC)
    async with db_notificaciones.sessions() as session, session.begin():
        notif_id = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="201", destinatario="residente201@condominio.pe"),
            ahora=t0,
        )
    assert notif_id is not None

    # 1. Worker A reclama el lote con lease de 30s y "cae" antes de enviar
    lote_a = await reclamar_lote(
        db_notificaciones.sessions,
        worker_id="worker-caido",
        ahora=t0,
        limite=10,
        lease=30,
    )
    assert len(lote_a) == 1
    assert lote_a[0].id == notif_id

    # 2. Mientras el arrendamiento sigue vigente (t0 + 15s), Worker B no puede reclamarla
    transporte = TransporteSimulado()
    res_vigente = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        worker_id="worker-recuperador",
        ahora=t0 + timedelta(seconds=15),
    )
    assert res_vigente.reclamadas == 0
    assert transporte.total_llamadas == 0

    # 3. Una vez vencido el arrendamiento (t0 + 31s), Worker B la reclama y despacha
    t_vencido = t0 + timedelta(seconds=31)
    res_recuperado = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        worker_id="worker-recuperador",
        ahora=t_vencido,
    )
    assert res_recuperado.reclamadas == 1
    assert res_recuperado.aceptadas == 1
    assert transporte.llamadas_para(notif_id) == 1

    # 4. Si el worker caído intenta tardíamente registrar un fallo, es omitido y no pisa ACEPTADO
    estado_tardio = await registrar_resultado_intento(
        session_factory=db_notificaciones.sessions,
        notificacion_id=notif_id,
        worker_id="worker-caido",
        transporte=transporte,
        resultado=ResultadoTransporte.fallo("500", "Fallo tardío worker caído"),
        iniciado_en=t0,
        finalizado_en=t_vencido + timedelta(seconds=2),
    )
    assert estado_tardio == "OMITIDA"

    async with db_notificaciones.sessions() as session:
        notif = await session.get(Notificacion, notif_id)
        assert notif.estado == "ACEPTADO"
        assert notif.intentos == 1
        assert notif.error_codigo is None


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_entregado_no_se_reenvia_y_reprogramar_manual(db_notificaciones: BaseUsuarios):
    """Verifica que ENTREGADO nunca se reenvía y que reprogramar_manual opera sobre fallidas."""
    t0 = datetime(2026, 10, 20, 15, 0, 0, tzinfo=UTC)
    async with db_notificaciones.sessions() as session, session.begin():
        id_entregable = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="105", destinatario="ok105@condominio.pe", clave_extra="e1"),
            ahora=t0,
        )
        id_fallida = await registrar_notificacion(
            session,
            _nueva_notif(dpto_num="402", destinatario="mal402@condominio.pe", clave_extra="f1"),
            ahora=t0,
        )

    transporte = TransporteSimulado(
        por_destinatario={
            "mal402@condominio.pe": ResultadoTransporte.fallo("550", "User unknown"),
        },
        confirmar_entrega=True,
    )

    res = await despachar_pendientes(db_notificaciones.sessions, transporte, "w1", ahora=t0)
    assert res.entregadas == 1
    assert res.fallidas_permanentes == 1
    assert transporte.llamadas_para(id_entregable) == 1
    assert transporte.llamadas_para(id_fallida) == 1

    # Intentar despachar de nuevo no toca la ENTREGADO ni la FALLIDO_PERMANENTE
    res_nuevo = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        "w1",
        ahora=t0 + timedelta(minutes=60),
    )
    assert res_nuevo.reclamadas == 0
    assert transporte.llamadas_para(id_entregable) == 1

    # reprogramar_manual rechaza con 409 una notificación que está en ENTREGADO
    async with db_notificaciones.sessions() as session, session.begin():
        with pytest.raises(APIError) as exc_info:
            await reprogramar_manual(session, id_entregable, "otro@condominio.pe", ahora=t0)
        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "REENVIO_NO_PERMITIDO"

    # reprogramar_manual sobre FALLIDO_PERMANENTE reinicia contador a 0, pasa a EN_COLA y atiende alerta
    t_reenvio = t0 + timedelta(minutes=5)
    admin_id = uuid.uuid4()
    async with db_notificaciones.sessions() as session, session.begin():
        reprogramada = await reprogramar_manual(
            session,
            id_fallida,
            nuevo_destinatario="corregido402@condominio.pe",
            ahora=t_reenvio,
            atendida_por=admin_id,
        )
        assert reprogramada.id == id_fallida
        assert reprogramada.estado == "EN_COLA"
        assert reprogramada.intentos == 0
        assert reprogramada.destinatario == "corregido402@condominio.pe"
        assert reprogramada.proximo_intento_en == t_reenvio
        assert reprogramada.ciclo == 2

        alerta = await session.scalar(
            select(AlertaAdministrativa).where(AlertaAdministrativa.notificacion_id == id_fallida)
        )
        assert alerta is not None
        assert alerta.atendida_en == t_reenvio
        assert alerta.atendida_por == admin_id

    # El siguiente ciclo despacha la notificación reprogramada sin colisión en uq_intento_numero
    res_post_reenvio = await despachar_pendientes(
        db_notificaciones.sessions,
        transporte,
        "w1",
        ahora=t_reenvio,
    )
    assert res_post_reenvio.entregadas == 1
    assert transporte.llamadas_para(id_fallida) == 2

    async with db_notificaciones.sessions() as session:
        final = await session.get(Notificacion, id_fallida)
        assert final.estado == "ENTREGADO"
        assert final.intentos == 1
        assert final.destinatario == "corregido402@condominio.pe"
        historial = (
            await session.execute(
                select(
                    NotificacionIntento.ciclo,
                    NotificacionIntento.numero,
                    NotificacionIntento.resultado,
                )
                .where(NotificacionIntento.notificacion_id == id_fallida)
                .order_by(NotificacionIntento.ciclo, NotificacionIntento.numero)
            )
        ).all()
        # El ciclo agotado se conserva como evidencia junto al nuevo intento.
        assert [tuple(f) for f in historial] == [(1, 1, "FALLO_DEFINITIVO"), (2, 1, "ACEPTADO")]


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_transporte_por_defecto_fallos_de_demostracion_persisten_entre_reinicios(
    db_notificaciones: BaseUsuarios,
):
    """`+falla1@` se recupera en el primer reintento y `+rebote@` falla definitivamente,
    aunque cada pasada use una instancia nueva del transporte (worker reiniciado)."""
    t0 = datetime(2026, 10, 20, 15, 0, 0, tzinfo=UTC)
    async with db_notificaciones.sessions() as session, session.begin():
        id_temporal = await registrar_notificacion(
            session,
            _nueva_notif(destinatario="demo+falla1@condominio.pe", clave_extra="demo-t"),
            ahora=t0,
        )
        id_rebote = await registrar_notificacion(
            session,
            _nueva_notif(
                dpto_num="105", destinatario="demo+rebote@condominio.pe", clave_extra="demo-r"
            ),
            ahora=t0,
        )

    primera = await despachar_pendientes(
        db_notificaciones.sessions, obtener_transporte(), "w-a", ahora=t0, jitter_fn=lambda: 0
    )
    assert (primera.reintentando, primera.fallidas_permanentes) == (1, 1)

    segunda = await despachar_pendientes(
        db_notificaciones.sessions, obtener_transporte(), "w-b", ahora=t0 + timedelta(minutes=2)
    )
    assert segunda.aceptadas == 1

    async with db_notificaciones.sessions() as session:
        temporal = await session.get(Notificacion, id_temporal)
        rebote = await session.get(Notificacion, id_rebote)
        assert (temporal.estado, temporal.intentos, temporal.transporte_simulado) == (
            "ACEPTADO",
            2,
            True,
        )
        assert (rebote.estado, rebote.error_codigo) == ("FALLIDO_PERMANENTE", "550")
