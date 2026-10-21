"""CON-73/74: PostgreSQL real, transacciones y workers independientes."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.core.security import decode_access_token
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import (
    EventoConsumido,
    IncidenciaEvento,
    IntentoNotificacion,
    Notificacion,
)
from src.modules.notificaciones.worker import procesar_uno, publicar_pendientes, recuperar_inciertos
from src.modules.pagos.solvencia import SolvenciaService
from src.modules.reservas.models import EventoReservaOutbox, Reserva
from src.modules.reservas.persistencia import ReservasPersistentesService
from src.modules.reservas.schemas import CancelarReservaRequest
from src.modules.reservas.service import CancelacionInvalidaException
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_catalogo_areas_db import turno

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
AREA = "11111111-1111-1111-1111-111111111101"


async def reservar(client, base):
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    respuesta = await client.post("/api/v1/reservas", headers=residente, json=turno(base, AREA))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json(), residente


async def evento(base):
    async with base.sessions() as db:
        return (await db.scalar(select(EventoReservaOutbox))).payload


async def test_reserva_auditoria_outbox_y_sesion_independiente(api_usuarios):
    client, base = api_usuarios
    reserva, residente = await reservar(client, base)
    await base.engine.dispose()
    listado = await client.get("/api/v1/reservas", headers=residente)
    assert listado.json() == [reserva]
    async with base.sessions() as db:
        assert (await db.get(Reserva, UUID(reserva["id"]))).moneda == "PEN"
        audit = await db.scalar(
            select(AuditoriaLogORM).where(AuditoriaLogORM.accion_ejecutada == "RESERVA_CONFIRMADA")
        )
        assert (
            audit.actor_id
            and audit.hash_actual
            and audit.estado_posterior["reserva_id"] == reserva["id"]
        )
        assert (await db.scalar(select(EventoReservaOutbox))).publicado_en is None


async def test_rollback_no_deja_reserva_auditoria_ni_evento(api_usuarios, monkeypatch):
    client, base = api_usuarios

    def fallar(*args, **kwargs):
        raise RuntimeError("fallo controlado antes del outbox")

    monkeypatch.setattr(ReservasPersistentesService, "evento", fallar)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    r = await client.post("/api/v1/reservas", headers=residente, json=turno(base, AREA))
    assert r.status_code == 500
    async with base.sessions() as db:
        assert await db.scalar(select(Reserva.id)) is None
        assert await db.scalar(select(EventoReservaOutbox.id)) is None
        assert (
            await db.scalar(
                select(AuditoriaLogORM.id).where(
                    AuditoriaLogORM.accion_ejecutada == "RESERVA_CONFIRMADA"
                )
            )
            is None
        )


async def test_diez_reservas_concurrentes_y_contiguas(api_usuarios):
    client, base = api_usuarios
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    respuestas = await asyncio.gather(
        *[
            client.post("/api/v1/reservas", headers=residente, json=turno(base, AREA))
            for _ in range(10)
        ]
    )
    assert sorted(r.status_code for r in respuestas) == [201] + [409] * 9
    assert all(
        r.json()["error_code"] == "HORARIO_NO_DISPONIBLE"
        for r in respuestas
        if r.status_code == 409
    )
    r = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, AREA, "16:00", "17:00")
    )
    assert r.status_code == 201
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Reserva)) == 2


async def test_consumo_concurrente_no_duplica_y_avisos_privados(api_usuarios):
    client, base = api_usuarios
    reserva, residente = await reservar(client, base)
    payload = await evento(base)
    resultados = await asyncio.gather(
        consumir(base.sessions, payload), consumir(base.sessions, payload)
    )
    assert sorted(resultados) == [0, 1]
    propios = await client.get("/api/v1/notificaciones/logs", headers=residente)
    assert propios.status_code == 200 and len(propios.json()) == 1
    assert propios.json()[0]["estado"] == "EN_COLA" and propios.json()[0]["intentos"] == 0
    ajeno = await login(client, "inquilino504@villabonita3.pe", "Inquilino123!")
    assert (await client.get("/api/v1/notificaciones/logs", headers=ajeno)).json() == []
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(EventoConsumido)) == 1
        log = await db.scalar(select(Notificacion))
        assert log.operacion_id == UUID(reserva["id"])
        assert "S/" in log.cuerpo and reserva["costo_reserva"] in log.cuerpo


async def test_reintento_sobrevive_sesion_y_workers_no_duplican(api_usuarios):
    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    ahora = datetime.now(UTC)
    llamadas = []

    def temporal(log, clave):
        llamadas.append(clave)
        return {"status": 503}

    resultados = await asyncio.gather(
        *[procesar_uno(base.sessions, temporal, ahora, jitter=lambda a, b: 0) for _ in range(2)]
    )
    assert sorted(resultados) == [False, True] and len(llamadas) == 1
    await base.engine.dispose()
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        assert log.intentos == 1 and log.proximo_reintento == ahora + timedelta(minutes=2)
        assert log.estado == "REINTENTANDO"
    assert not await procesar_uno(base.sessions, ahora=ahora + timedelta(seconds=119))
    assert await procesar_uno(base.sessions, ahora=ahora + timedelta(minutes=2))
    assert not await procesar_uno(base.sessions, ahora=ahora + timedelta(hours=1))
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        assert log.estado == "ENVIADO" and log.transporte == "SIMULADO" and log.intentos == 2
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 2


async def test_agotamiento_e_incierto_no_reenvian(api_usuarios):
    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    ahora = datetime.now(UTC)
    for minutos in (0, 2, 12, 42):
        assert await procesar_uno(
            base.sessions,
            lambda n, k: {"status": 503},
            ahora + timedelta(minutes=minutos),
            jitter=lambda a, b: 0,
        )
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        assert log.estado == "FALLIDO_PERMANENTE" and log.intentos == 4
    assert not await procesar_uno(base.sessions, ahora=ahora + timedelta(days=1))


@pytest.mark.parametrize("segundos", [-1, 0, 1])
async def test_cancelacion_limite_y_repeticion_atomica(api_usuarios, segundos):
    client, base = api_usuarios
    reserva, residente = await reservar(client, base)
    actor = decode_access_token(residente["Authorization"].split()[1])
    from src.modules.reservas.repository import instantes

    async with base.sessions() as db:
        r = await db.get(Reserva, UUID(reserva["id"]))
        limite = instantes(r)[0] - timedelta(hours=24)
    async with base.sessions() as db:
        servicio = ReservasPersistentesService(SolvenciaService(db))
        if segundos > 0:
            with pytest.raises(CancelacionInvalidaException):
                await servicio.cancelar(
                    r.id,
                    CancelarReservaRequest(es_admin=True),
                    actor,
                    limite + timedelta(seconds=segundos),
                )
            return
        respuesta = await servicio.cancelar(r.id, None, actor, limite + timedelta(seconds=segundos))
    async with base.sessions() as db:
        repetida = await ReservasPersistentesService(SolvenciaService(db)).cancelar(
            r.id, None, actor
        )
        assert repetida == respuesta
        assert await db.scalar(select(func.count()).select_from(EventoReservaOutbox)) == 2
    disponible = await client.get(
        f"/api/v1/areas/{AREA}/disponibilidad",
        headers=residente,
        params={"fecha": reserva["fecha_reserva"]},
    )
    assert disponible.json() == []


async def test_evento_invalido_se_conserva_sin_avisos(api_usuarios):
    _, base = api_usuarios
    payload = {"event_type": "Desconocido", "password": "no guardar"}
    assert await consumir(base.sessions, payload) is None
    assert await consumir(base.sessions, payload) is None
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(IncidenciaEvento)) == 1
        assert await db.scalar(select(Notificacion.id)) is None


async def test_relay_recupera_despues_de_fallo_y_conserva_event_id(api_usuarios):
    client, base = api_usuarios
    await reservar(client, base)

    class Redis:
        def __init__(self):
            self.falla = True
            self.payloads = []

        async def xadd(self, stream, values):
            self.payloads.append(values)
            if self.falla:
                raise ConnectionError("simulado")

    redis = Redis()
    with pytest.raises(ConnectionError):
        await publicar_pendientes(redis, base.sessions)
    redis.falla = False
    await publicar_pendientes(redis, base.sessions)
    assert redis.payloads[0] == redis.payloads[1]
    async with base.sessions() as db:
        assert (await db.scalar(select(EventoReservaOutbox))).publicado_en is not None


async def test_recuperar_aceptacion_incierta_sin_duplicar(api_usuarios):
    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    ahora = datetime.now(UTC)
    async with base.sessions() as db, db.begin():
        log = await db.scalar(select(Notificacion))
        log.intentos = 1
        db.add(
            IntentoNotificacion(
                notificacion_id=log.id, ciclo=1, numero=1, iniciado_en=ahora - timedelta(minutes=6)
            )
        )
    await recuperar_inciertos(base.sessions, ahora)
    assert not await procesar_uno(base.sessions, ahora=ahora)
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        assert log.estado == "FALLIDO_PERMANENTE" and "INCIERTA" in log.error_mensaje


async def test_lease_durable_excluye_otro_worker_durante_el_transporte(api_usuarios):
    from threading import Event

    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    iniciado, continuar = Event(), Event()

    def transporte(log, clave):
        iniciado.set()
        assert continuar.wait(10)
        return {"status": 200, "message_id": clave}

    tarea = asyncio.create_task(procesar_uno(base.sessions, transporte))
    try:
        assert await asyncio.to_thread(iniciado.wait, 10)
        async with base.sessions() as db:
            log = await db.scalar(select(Notificacion))
            assert log.bloqueado_hasta > datetime.now(UTC) and log.intentos == 1
        assert not await procesar_uno(base.sessions)
    finally:
        continuar.set()
        await tarea
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        assert log.estado == "ENVIADO" and log.bloqueado_hasta is None
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 1


async def test_pago_confirmado_origina_aviso_desde_outbox_real(api_pagos):
    from src.modules.pagos.models_persistencia import EventoPagoOutbox
    from src.tests.integration.test_pagos_db import login as login_pago
    from src.tests.integration.test_pagos_db import reportar

    client, base = api_pagos
    residente = await login_pago(client)
    response = await reportar(client, residente)
    assert response.status_code == 202
    junta = await login_pago(client, "admin", "Admin123!")
    response = await client.post(
        f"/api/v1/pagos/{response.json()['comprobante_id']}/conciliar",
        headers=junta,
        json={"decision": "APROBADO"},
    )
    assert response.status_code == 200
    async with base.sessions() as db:
        payloads = [e.payload for e in await db.scalars(select(EventoPagoOutbox))]
    for payload in payloads:
        assert await consumir(base.sessions, payload) == 1
    logs = (await client.get("/api/v1/notificaciones/logs", headers=residente)).json()
    assert len(logs) == 2
    aprobado = next(n for n in logs if n["tipo_evento"] == "NOTIF_PAGO_CONCILIADO")
    assert "170.00" in aprobado["cuerpo"] and "0.00" in aprobado["cuerpo"]


async def test_utc_historico_y_bloqueos_fusionados_sin_datos_privados(api_usuarios):
    from datetime import time
    from zoneinfo import ZoneInfo

    from src.modules.reservas.models import BloqueoArea

    client, base = api_usuarios
    reserva, residente = await reservar(client, base)
    async with base.sessions() as db, db.begin():
        r = await db.get(Reserva, UUID(reserva["id"]))
        r.zona_horaria, r.hora_inicio, r.hora_fin = "UTC", time(19), time(21)
        r.usuario_id = None
        db.add(
            BloqueoArea(
                area_id=r.area_id,
                inicio=datetime.combine(r.fecha_reserva, time(15), ZoneInfo("America/Lima")),
                fin=datetime.combine(r.fecha_reserva, time(17), ZoneInfo("America/Lima")),
            )
        )
    r = await client.get(
        f"/api/v1/areas/{AREA}/disponibilidad",
        headers=residente,
        params={"fecha": reserva["fecha_reserva"]},
    )
    assert r.json() == [{"hora_inicio": "14:00:00", "hora_fin": "17:00:00"}]
    rechazado = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, AREA, "16:00", "17:00")
    )
    assert rechazado.status_code == 409
    contiguo = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, AREA, "17:00", "18:00")
    )
    assert contiguo.status_code == 201


async def test_fallo_definitivo_y_ciclo_manual_no_borran_intentos(api_usuarios):
    from src.modules.usuarios.models import Usuario

    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    assert await procesar_uno(
        base.sessions, lambda n, k: {"status": 500, "error": "550 User unknown"}
    )
    admin = await login(client)
    async with base.sessions() as db:
        log = await db.scalar(select(Notificacion))
        assert log.estado == "FALLIDO_PERMANENTE" and log.intentos == 1
        rid, uid = log.id, log.usuario_destinatario_id
    ruta = f"/api/v1/notificaciones/reenviar/{rid}"
    assert (await client.post(ruta, headers=admin)).status_code == 409
    assert (
        await client.post(ruta, headers=admin, json={"nuevo_destinatario": "ajeno@ejemplo.test"})
    ).status_code == 422
    async with base.sessions() as db, db.begin():
        u = await db.get(Usuario, uid)
        u.email = "corregido@ejemplo.test"
    respuesta = await client.post(
        ruta, headers=admin, json={"nuevo_destinatario": "corregido@ejemplo.test"}
    )
    assert respuesta.status_code == 200 and respuesta.json()["ciclo"] == 2
    assert respuesta.json()["intentos"] == 0
    assert await procesar_uno(base.sessions)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 2
        assert (await db.get(Notificacion, rid)).estado == "ENVIADO"
        assert await db.scalar(
            select(AuditoriaLogORM.id).where(
                AuditoriaLogORM.accion_ejecutada == "NOTIFICACION_REENVIO_MANUAL"
            )
        )


async def test_no_envia_a_destinatario_revocado(api_usuarios):
    from src.modules.usuarios.models import UsuarioDepartamento

    client, base = api_usuarios
    await reservar(client, base)
    await consumir(base.sessions, await evento(base))
    async with base.sessions() as db, db.begin():
        log = await db.scalar(select(Notificacion))
        vinculo = await db.scalar(
            select(UsuarioDepartamento).where(
                UsuarioDepartamento.usuario_id == log.usuario_destinatario_id,
                UsuarioDepartamento.departamento_id == log.departamento_id,
            )
        )
        vinculo.es_activo = False

    def no_enviar(*args):
        pytest.fail("No debe ejecutarse el transporte para un destinatario revocado")

    assert await procesar_uno(base.sessions, no_enviar)
    async with base.sessions() as db:
        assert (await db.scalar(select(Notificacion))).estado == "FALLIDO_PERMANENTE"
        assert await db.scalar(select(IntentoNotificacion.id)) is None


async def test_eventos_reserva_cumplen_esquemas_publicados(api_usuarios):
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource

    client, base = api_usuarios
    reserva, residente = await reservar(client, base)
    assert (
        await client.post(f"/api/v1/reservas/{reserva['id']}/cancelar", headers=residente)
    ).status_code == 200
    ruta = Path("specs/03-contracts/events/schemas").resolve()
    registry = Registry().with_resources(
        (p.as_uri(), Resource.from_contents(json.loads(p.read_text()))) for p in ruta.glob("*.json")
    )
    async with base.sessions() as db:
        eventos = list(await db.scalars(select(EventoReservaOutbox)))
    for e in eventos:
        archivo = (
            "reserva-confirmada.v1.schema.json"
            if e.payload["event_type"] == "ReservaConfirmadaEvent"
            else "reserva-cancelada.v1.schema.json"
        )
        Draft202012Validator(
            {"$ref": (ruta / archivo).as_uri()}, registry=registry, format_checker=FormatChecker()
        ).validate(e.payload)


async def test_validacion_de_reservas_no_reproduce_entradas_sensibles(api_usuarios):
    client, base = api_usuarios
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    response = await client.post(
        "/api/v1/reservas",
        headers=residente,
        json={**turno(base, AREA), "password": "no-divulgar-esta-entrada"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "DATOS_RESERVA_INVALIDOS"
    assert "errores" in response.json()["detalles"]
    assert "no-divulgar-esta-entrada" not in response.text


@pytest.mark.parametrize("version_invalida", [False, True])
async def test_recupera_outbox_sin_redis_y_no_cicla_eventos_invalidos(
    api_usuarios, version_invalida
):
    from src.modules.notificaciones.worker import recuperar_eventos

    client, base = api_usuarios
    await reservar(client, base)
    if version_invalida:
        async with base.sessions() as db, db.begin():
            e = await db.scalar(select(EventoReservaOutbox))
            e.payload = {**e.payload, "schema_version": 999}
    await recuperar_eventos(base.sessions)
    await recuperar_eventos(base.sessions)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == (
            0 if version_invalida else 1
        )
        marcador = await db.scalar(select(EventoConsumido))
        assert marcador.consumidor == (
            "notificaciones-descartado-v1" if version_invalida else "notificaciones-v1"
        )
        assert await db.scalar(select(func.count()).select_from(IncidenciaEvento)) == int(
            version_invalida
        )


async def test_comunicado_solo_encola_contactos_sql_autorizados(api_usuarios):
    client, base = api_usuarios
    from src.modules.usuarios.demo import id_demo
    from src.modules.usuarios.models import UsuarioDepartamento
    from src.tests.pagos_db import did

    # Una identidad puede recibir comunicaciones distintas de dos unidades.
    async with base.sessions() as db, db.begin():
        db.add(
            UsuarioDepartamento(
                usuario_id=id_demo("residente102@villabonita3.pe"),
                departamento_id=did("504"),
                tipo_relacion="COPROPIETARIO",
                es_activo=True,
            )
        )
    admin = await login(client)
    response = await client.post(
        "/api/v1/notificaciones/comunicado-masivo",
        headers=admin,
        json={
            "condominio_id": base.cid,
            "titulo": "Aviso de prueba",
            "mensaje": "Comunicado sobre áreas comunes.",
        },
    )
    assert response.status_code == 202
    assert response.json()["generadas"] == 4
    assert response.json()["estado_general"] == "EN_COLA"
    async with base.sessions() as db:
        logs = list(await db.scalars(select(Notificacion)))
        assert len(logs) == 4 and all(n.estado == "EN_COLA" and n.intentos == 0 for n in logs)
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (
        await client.post(
            "/api/v1/notificaciones/comunicado-masivo",
            headers=auditor,
            json={
                "condominio_id": base.cid,
                "titulo": "Aviso de prueba",
                "mensaje": "No puede escribir el auditor.",
            },
        )
    ).status_code == 403
