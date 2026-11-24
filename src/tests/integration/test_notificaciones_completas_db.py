"""Cierre EMAIL con PostgreSQL, transportes sustituidos y audiencias reales."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.eventos_mailjet import EventoMailjet, aplicar_evento
from src.modules.notificaciones.models import (
    Comunicado,
    ContactoBloqueado,
    EventoSolvenciaOutbox,
    IntentoNotificacion,
    Notificacion,
    PoliticaNotificaciones,
)
from src.modules.notificaciones.recordatorios import generar_recordatorios
from src.modules.notificaciones.worker import procesar_uno, recuperar_eventos
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario
from src.tests.integration.test_alertas_notificaciones_db import encolar
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio
from src.tests.integration.test_convergencia_con72 import revisar
from src.tests.integration.test_notificaciones_pagos_db import reportar_id
from src.tests.integration.test_pagos_db import login as login_pago
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
R = "/api/v1/notificaciones"
UID = id_demo("residente102@villabonita3.pe")


def contenido(base, **extra):
    return {
        "condominio_id": base.cid, "titulo": "Comunicado de prueba",
        "mensaje": "Este comunicado no se envía a Mailjet.",
        "usuario_ids": [str(UID)], **extra,
    }


async def test_previsualizacion_confirmacion_concurrente_y_resumen(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    vista = await client.post(f"{R}/comunicados/previsualizar", headers=admin, json=contenido(base))
    assert vista.status_code == 201, vista.text
    datos = vista.json()
    assert datos["cantidad"] == 1 and datos["destinatarios"][0]["usuario_id"] == str(UID)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 0
    respuestas = await asyncio.gather(*[
        client.post(f"{R}/comunicados/{datos['id']}/confirmar", headers=admin) for _ in range(2)
    ])
    assert all(r.status_code == 202 for r in respuestas)
    assert respuestas[0].json() == respuestas[1].json()
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM).where(
            AuditoriaLogORM.accion_ejecutada == "COMUNICADO_CONFIRMADO"
        )) == 1
    resumen = await client.get(f"{R}/comunicados?condominio_id={base.cid}", headers=admin)
    assert resumen.json()[0]["conteos"] == {"EN_COLA": 1}


async def test_audiencia_cambiada_caducidad_y_aislamiento(api_usuarios, monkeypatch):
    client, base = api_usuarios
    admin = await login(client)
    for cambio in ("contacto", "caducado"):
        vista = (await client.post(f"{R}/comunicados/previsualizar", headers=admin, json=contenido(base))).json()
        async with base.sessions() as db, db.begin():
            if cambio == "contacto":
                (await db.get(Usuario, UID)).email = "nuevo@example.test"
            else:
                (await db.get(Comunicado, UUID(vista["id"]))).creado_en -= timedelta(minutes=16)
        r = await client.post(f"{R}/comunicados/{vista['id']}/confirmar", headers=admin)
        assert r.status_code == 409
    r = await client.post(f"{R}/comunicados/previsualizar", headers=admin,
                          json=contenido(base, edificio_ids=[str(uuid4())]))
    assert r.status_code == 422
    otro = await otro_condominio(base)
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    r = await client.post(f"{R}/comunicados/previsualizar", headers=junta,
                          json=contenido(base, condominio_id=str(otro)))
    assert r.status_code == 403
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (await client.get(f"{R}/comunicados?condominio_id={base.cid}", headers=auditor)).status_code == 200
    assert (await client.post(f"{R}/comunicados/previsualizar", headers=auditor, json=contenido(base))).status_code == 403
    residente = await login(client, "nuevo@example.test", "Residente123!")
    assert (await client.get(f"{R}/audiencia?condominio_id={base.cid}", headers=residente)).status_code == 403
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert (await client.post(f"{R}/comunicado-masivo", headers=admin,
                             json={k: v for k, v in contenido(base).items() if k != "usuario_ids"})).status_code == 409


@pytest.mark.parametrize("decision", ["ACEPTADO", "NO_ACEPTADO", "DESCARTAR"])
async def test_resolver_incierto_con_auditoria(api_usuarios, monkeypatch, decision):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    nid, admin = await encolar(client, base, "destino@example.test")
    assert await procesar_uno(base.sessions, lambda *a: {"status": 0, "incierto": True})
    ruta = f"{R}/{nid}/resolver-incierto"
    datos = {"ciclo": 1, "intento": 1, "decision": decision, "referencia": "Revisión manual Mailjet referencia 123"}
    if decision == "NO_ACEPTADO":
        assert (await client.post(ruta, headers=admin, json=datos)).status_code == 422
        datos["confirmar_no_aceptado"] = True
    if decision == "ACEPTADO":
        assert (await client.post(ruta, headers=admin, json=datos)).status_code == 422
        datos["message_id"] = "123"
    r = await client.post(ruta, headers=admin, json=datos)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == {"ACEPTADO": "ENVIADO", "NO_ACEPTADO": "EN_COLA", "DESCARTAR": "OMITIDO"}[decision]
    assert (await client.post(ruta, headers=admin, json=datos)).status_code == 409
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 1
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM).where(
            AuditoriaLogORM.accion_ejecutada == "NOTIFICACION_INCIERTA_RESUELTA"
        )) == 1


async def test_supresion_impide_nuevos_envios_y_reactivacion(api_usuarios, monkeypatch):
    client, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    nid, admin = await encolar(client, base, "destino@example.test")
    assert await procesar_uno(base.sessions, lambda *a: {"status": 200, "message_id": "123"})
    await aplicar_evento(EventoMailjet(
        event="bounce", MessageID=123, CustomID=f"{nid}-1-1", email="destino@example.test"
    ), base.sessions)
    nid2, _ = await encolar(client, base, "destino@example.test")
    assert await procesar_uno(base.sessions, lambda *a: pytest.fail("contacto suprimido"))
    async with base.sessions() as db:
        assert (await db.get(Notificacion, nid2)).estado == "OMITIDO"
        assert (await db.get(Notificacion, nid2)).intentos == 0
    r = await client.get(f"{R}/contactos-bloqueados?condominio_id={base.cid}", headers=admin)
    assert r.json()[0]["email"] == "destino@example.test"
    vista = await client.post(f"{R}/comunicados/previsualizar", headers=admin, json=contenido(base))
    assert vista.json()["cantidad"] == 0
    r = await client.post(f"{R}/contactos-bloqueados/{base.cid}/reactivar", headers=admin,
                          json={"email": "destino@example.test", "motivo": "Contacto corregido y verificado manualmente"})
    assert r.status_code == 200, r.text
    async with base.sessions() as db:
        assert await db.get(ContactoBloqueado, (UUID(base.cid), "destino@example.test")) is None


async def test_politica_cursor_recuperacion_y_saldo_al_enviar(api_usuarios, monkeypatch):
    client, base = api_usuarios
    admin = await login(client)
    ruta = f"{R}/configuracion/{base.cid}"
    assert (await client.put(ruta, headers=admin, json={"dias": [1, 1]})).status_code == 422
    assert (await client.put(ruta, headers=admin, json={"dias": [31]})).status_code == 422
    r = await client.put(ruta, headers=admin, json={"dias": [1, 0], "hora": 8, "habilitado": True})
    assert r.status_code == 200, r.text
    ahora = datetime(2026, 11, 21, 13, tzinfo=UTC)
    cuota = CuotaMantenimiento(
        departamento_id=did("102"), periodo="2026-11", monto_ordinario=100,
        monto_total_exigible=100, fecha_emision=ahora.date(),
        fecha_vencimiento=(ahora + timedelta(days=1)).date(),
    )
    async with base.sessions() as db, db.begin():
        (await db.get(PoliticaNotificaciones, UUID(base.cid))).ultima_fecha = ahora.date() - timedelta(days=1)
        db.add(cuota)
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    await generar_recordatorios(base.sessions, ahora)
    await generar_recordatorios(base.sessions, ahora + timedelta(days=3))
    await generar_recordatorios(base.sessions, ahora + timedelta(days=3))
    async with base.sessions() as db, db.begin():
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 2
        (await db.get(CuotaMantenimiento, cuota.id)).monto_pagado = 25
    recibidos = []
    def enviar(log, clave):
        recibidos.append(log.cuerpo)
        return {"status": 200, "message_id": "123"}
    while await procesar_uno(base.sessions, enviar):
        pass
    assert len(recibidos) == 2 and all("75.00" in texto for texto in recibidos)
    resumen = await client.get(f"{R}/operacion?condominio_id={base.cid}", headers=admin)
    assert resumen.status_code == 200 and resumen.json()["conteos"]["ENVIADO"] == 2


async def test_solvencia_outbox_unico_y_consumo(api_pagos):
    client, base = api_pagos
    residente = await login_pago(client)
    junta = await login_pago(client, "admin", "Admin123!")
    pid = await reportar_id(client, residente, "SOLVENCIA-EMAIL", "1000.00")
    r = await revisar(client, junta, pid, "APROBADO", None)
    assert r.status_code == 200, r.text
    assert (await revisar(client, junta, pid, "APROBADO", None)).status_code == 200
    await recuperar_eventos(base.sessions)
    await recuperar_eventos(base.sessions)
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(EventoSolvenciaOutbox)) == 1
        avisos = list(await db.scalars(select(Notificacion).where(
            Notificacion.tipo_evento == "NOTIF_RESTRICCION_LEVANTADA"
        )))
        assert len(avisos) == 1 and "reservas" in avisos[0].cuerpo


async def test_migracion_reversible_vacia_y_guardia_con_historia(api_usuarios):
    from importlib import import_module

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    _, base = api_usuarios
    revision = import_module("migrations.versions.20261121_0022_notificaciones_completas")
    def ejecutar(conn, funcion):
        with Operations.context(MigrationContext.configure(conn)):
            funcion()
    async with base.engine.begin() as conn:
        consulta = text("SELECT id,password_hash,esta_activo FROM usuarios ORDER BY id")
        antes = (await conn.execute(consulta)).all()
        await conn.run_sync(ejecutar, revision.downgrade)
        await conn.run_sync(ejecutar, revision.upgrade)
        assert (await conn.execute(consulta)).all() == antes
    async with base.sessions() as db, db.begin():
        db.add(PoliticaNotificaciones(condominio_id=UUID(base.cid)))
    async with base.engine.begin() as conn:
        with pytest.raises(DBAPIError, match="historial"):
            async with conn.begin_nested():
                await conn.run_sync(ejecutar, revision.downgrade)
        assert await conn.scalar(text("SELECT count(*) FROM politicas_notificaciones")) == 1


async def test_audiencia_por_unidad_y_un_aviso_por_usuario(api_usuarios):
    from src.modules.usuarios.models import UsuarioDepartamento
    client, base = api_usuarios
    async with base.sessions() as db, db.begin():
        db.add(UsuarioDepartamento(
            usuario_id=UID, departamento_id=did("504"), tipo_relacion="COPROPIETARIO", es_activo=True
        ))
    admin = await login(client)
    response = await client.get(f"{R}/audiencia?condominio_id={base.cid}", headers=admin)
    assert response.status_code == 200, response.text
    opciones = response.json()
    edificio = next(d["edificio_id"] for d in opciones if d["departamento_id"] == str(did("504")))
    r = await client.post(f"{R}/comunicados/previsualizar", headers=admin, json=contenido(
        base, usuario_ids=[], edificio_ids=[edificio], departamento_ids=[str(did("504"))],
    ))
    assert r.status_code == 201, r.text
    assert all(d["departamento_id"] == str(did("504")) for d in r.json()["destinatarios"])
    todo = await client.post(f"{R}/comunicados/previsualizar", headers=admin,
                             json=contenido(base, usuario_ids=[]))
    usuarios = [d["usuario_id"] for d in todo.json()["destinatarios"]]
    assert len(usuarios) == len(set(usuarios)) == 3


async def test_politica_put_repetido_conserva_cursor_y_permisos(api_usuarios):
    client, base = api_usuarios
    admin = await login(client)
    datos = {"dias": [3, 0], "hora": 9, "habilitado": False}
    ruta = f"{R}/configuracion/{base.cid}"
    assert (await client.put(ruta, headers=admin, json=datos)).status_code == 200
    async with base.sessions() as db, db.begin():
        (await db.get(PoliticaNotificaciones, UUID(base.cid))).ultima_fecha = datetime(2026, 10, 1).date()
    assert (await client.put(ruta, headers=admin, json=datos)).status_code == 200
    async with base.sessions() as db:
        assert (await db.get(PoliticaNotificaciones, UUID(base.cid))).ultima_fecha.isoformat() == "2026-10-01"
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM).where(
            AuditoriaLogORM.accion_ejecutada == "NOTIFICACIONES_CONFIGURADAS"
        )) == 1
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (await client.get(ruta, headers=auditor)).status_code == 200
    assert (await client.put(ruta, headers=auditor, json=datos)).status_code == 403
    assert (await client.post(f"{R}/comunicados/previsualizar", headers=admin,
                             json=contenido(base, titulo="     "))).status_code == 422


async def test_job_persiste_resultado_y_fallo_sin_secretos(api_usuarios, monkeypatch):
    from unittest.mock import AsyncMock

    from src.core import jobs
    from src.modules.notificaciones import recordatorios, worker
    from src.modules.notificaciones.models import EstadoJobNotificaciones
    _, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    monkeypatch.setattr(jobs, "AsyncSessionLocal", base.sessions)
    for modulo, nombre in ((jobs, "recuperar_eventos"), (worker, "recuperar_inciertos"),
                           (recordatorios, "generar_recordatorios")):
        monkeypatch.setattr(modulo, nombre, AsyncMock())
    enviar = AsyncMock(return_value=False)
    monkeypatch.setattr(worker, "procesar_uno", enviar)
    await jobs.ejecutar_notificaciones()
    async with base.sessions() as db:
        assert (await db.get(EstadoJobNotificaciones, "correo")).estado == "COMPLETADO"
    enviar.side_effect = RuntimeError("sin datos sensibles")
    with pytest.raises(RuntimeError):
        await jobs.ejecutar_notificaciones()
    async with base.sessions() as db:
        job = await db.get(EstadoJobNotificaciones, "correo")
        assert job.estado == "INCOMPLETO" and job.fin >= job.inicio


async def test_primer_tick_antes_de_hora_conserva_dia_para_recuperacion(api_usuarios, monkeypatch):
    _, base = api_usuarios
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    ahora = datetime(2026, 11, 21, 12, tzinfo=UTC)
    async with base.sessions() as db, db.begin():
        db.add(CuotaMantenimiento(
            departamento_id=did("102"), periodo="2026-11", monto_ordinario=100,
            monto_total_exigible=100, fecha_emision=ahora.date(),
            fecha_vencimiento=ahora.date() + timedelta(days=3),
        ))
    await generar_recordatorios(base.sessions, ahora)
    async with base.sessions() as db:
        assert (await db.get(PoliticaNotificaciones, UUID(base.cid))).ultima_fecha.isoformat() == "2026-11-20"
    await generar_recordatorios(base.sessions, ahora + timedelta(days=1, hours=2))
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1
