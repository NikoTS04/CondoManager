"""CON-37: alertas administrativas por fallos permanentes sobre PostgreSQL real."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.notificaciones.alertas import crear_alerta
from src.modules.notificaciones.models import (
    AlertaNotificacion,
    IntentoNotificacion,
    Notificacion,
)
from src.modules.notificaciones.worker import procesar_uno, recuperar_inciertos
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario
from src.tests import usuarios_db
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
RUTA = "/api/v1/notificaciones"
SIN_JITTER = {"jitter": lambda a, b: 0}
HASTA_ALERTAS = (
    "20261020_0009_pagos_persistentes",
    "20261020_0012_reservas_notificaciones",
    "20261021_0012_cancelaciones_reserva",
    "20261021_0013_convergencia_con72",
    "20261021_0014_unir_reservas_y_convergencia",
    "20261021_0015_alertas_notificaciones",
)


@pytest.fixture(autouse=True)
def esquema_con_alertas(monkeypatch):
    """El esquema aislado debe incluir la cola de notificaciones y la tabla de alertas."""
    original = usuarios_db.migrar
    pendientes = tuple(r for r in HASTA_ALERTAS if r not in usuarios_db.REVISIONES)
    monkeypatch.setattr(
        usuarios_db,
        "migrar",
        lambda connection, revisiones=None: original(
            connection, tuple(revisiones or usuarios_db.REVISIONES) + pendientes
        ),
    )


async def encolar(client, base, email):
    """Cambia el correo del residente 102 y registra un aviso manual hacia él."""
    async with base.sessions() as db, db.begin():
        usuario = await db.get(Usuario, id_demo("residente102@villabonita3.pe"))
        usuario.email = email
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    respuesta = await client.post(
        f"{RUTA}/despachar",
        headers=junta,
        json={
            "condominio_id": base.cid,
            "departamento_id": str(did("102")),
            "tipo_evento": "NOTIF_COMUNICADO_GENERAL",
            "canal": "EMAIL",
            "destinatario": email,
            "contexto": {
                "titulo": "Aviso de prueba",
                "mensaje": "Texto del aviso",
                "remitente": "Junta",
            },
        },
    )
    assert respuesta.status_code == 202, respuesta.text
    return UUID(respuesta.json()["id"]), junta


async def alertas(base, nid=None):
    async with base.sessions() as db:
        consulta = select(AlertaNotificacion).order_by(AlertaNotificacion.creada_en)
        if nid:
            consulta = consulta.where(AlertaNotificacion.notificacion_id == nid)
        return list(await db.scalars(consulta))


async def estado(base, nid):
    async with base.sessions() as db:
        log = await db.get(Notificacion, nid)
        return log.estado, log.intentos


async def test_falla1_reintenta_y_se_recupera_sin_alerta(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana+falla1@ejemplo.test")
    ahora = datetime.now(UTC)
    assert await procesar_uno(base.sessions, ahora=ahora, **SIN_JITTER)
    assert await estado(base, nid) == ("REINTENTANDO", 1)
    assert not await procesar_uno(base.sessions, ahora=ahora + timedelta(seconds=119))
    # Una llamada nueva del worker, como tras un reinicio, continúa el mismo contador.
    assert await procesar_uno(base.sessions, ahora=ahora + timedelta(minutes=2))
    assert await estado(base, nid) == ("ENVIADO", 2)
    assert await alertas(base) == []


async def test_rebote_falla_de_inmediato_con_una_sola_alerta(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana+rebote@ejemplo.test")
    ahora = datetime.now(UTC)
    assert await procesar_uno(base.sessions, ahora=ahora)
    assert await estado(base, nid) == ("FALLIDO_PERMANENTE", 1)
    for dias in (0, 1, 2):
        assert not await procesar_uno(base.sessions, ahora=ahora + timedelta(days=dias))
    await recuperar_inciertos(base.sessions, ahora + timedelta(days=3))
    [alerta] = await alertas(base, nid)
    assert alerta.tipo == "ERROR_DEFINITIVO" and alerta.ciclo == 1
    assert alerta.mensaje == (
        "El correo del residente del Dpto. 102 rebotó. Actualice los datos de contacto."
    )
    assert "@" not in alerta.mensaje and alerta.atendida_en is None
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 1


async def test_cuatro_intentos_agotados_generan_una_alerta(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana+falla9@ejemplo.test")
    ahora = datetime.now(UTC)
    for minutos in (0, 2, 12, 42):
        assert await procesar_uno(
            base.sessions, ahora=ahora + timedelta(minutes=minutos), **SIN_JITTER
        )
        if minutos < 42:
            assert await alertas(base) == []
    assert await estado(base, nid) == ("FALLIDO_PERMANENTE", 4)
    assert not await procesar_uno(base.sessions, ahora=ahora + timedelta(days=1))
    [alerta] = await alertas(base, nid)
    assert alerta.tipo == "INTENTOS_AGOTADOS" and "Dpto. 102" in alerta.mensaje


async def test_aceptacion_incierta_genera_alerta_una_vez(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    ahora = datetime.now(UTC)
    async with base.sessions() as db, db.begin():
        log = await db.get(Notificacion, nid)
        log.intentos = 1
        db.add(
            IntentoNotificacion(
                notificacion_id=nid, ciclo=1, numero=1, iniciado_en=ahora - timedelta(minutes=6)
            )
        )
    await recuperar_inciertos(base.sessions, ahora)
    await recuperar_inciertos(base.sessions, ahora + timedelta(minutes=1))
    [alerta] = await alertas(base, nid)
    assert alerta.tipo == "ACEPTACION_INCIERTA"


async def test_destinatario_invalido_y_proveedor_no_configurado(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana@ejemplo.test")
    async with base.sessions() as db, db.begin():
        (await db.get(Usuario, id_demo("residente102@villabonita3.pe"))).email = "otro@ejemplo.test"
    assert await procesar_uno(base.sessions, lambda *a: pytest.fail("sin transporte"))
    [alerta] = await alertas(base, nid)
    assert alerta.tipo == "DESTINATARIO_INVALIDO"

    nid2, _ = await encolar(client, base, "ana2@ejemplo.test")
    async with base.sessions() as db, db.begin():
        (await db.get(Notificacion, nid2)).transporte = "PROVEEDOR"
    assert await procesar_uno(base.sessions, lambda *a: pytest.fail("sin transporte"))
    [alerta2] = await alertas(base, nid2)
    assert alerta2.tipo == "PROVEEDOR_NO_CONFIGURADO"


async def test_sin_duplicados_con_workers_y_sesiones_nuevas(api_usuarios):
    client, base = api_usuarios
    nid, _ = await encolar(client, base, "ana+rebote@ejemplo.test")
    ahora = datetime.now(UTC)
    resultados = await asyncio.gather(
        *[procesar_uno(base.sessions, ahora=ahora, **SIN_JITTER) for _ in range(3)]
    )
    assert resultados.count(True) == 1
    await base.engine.dispose()
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 1
        assert await db.scalar(select(func.count()).select_from(AlertaNotificacion)) == 1
    # Insertar de nuevo el mismo (notificación, ciclo, tipo) es un no-op.
    async with base.sessions() as db, db.begin():
        log = await db.get(Notificacion, nid)
        await crear_alerta(db, log, "ERROR_DEFINITIVO")
        await crear_alerta(db, log, "INTENTOS_AGOTADOS")
    tipos = sorted(a.tipo for a in await alertas(base, nid))
    assert tipos == ["ERROR_DEFINITIVO", "INTENTOS_AGOTADOS"]


async def test_api_lectura_por_rol_y_contexto(api_usuarios):
    client, base = api_usuarios
    nid, junta = await encolar(client, base, "ana+rebote@ejemplo.test")
    assert await procesar_uno(base.sessions, ahora=datetime.now(UTC))
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    residente = await login(client, "inquilino504@villabonita3.pe", "Inquilino123!")
    for headers in (junta, auditor):
        r = await client.get(f"{RUTA}/alertas", headers=headers)
        assert r.status_code == 200, r.text
        [dto] = r.json()
        assert dto["notificacion_id"] == str(nid) and dto["estado"] == "ABIERTA"
        assert dto["departamento_numero"] == "102" and dto["tipo"] == "ERROR_DEFINITIVO"
        assert dto["tipo_evento"] == "NOTIF_COMUNICADO_GENERAL" and dto["atendida_en"] is None
        assert dto["condominio_id"] == base.cid and dto["ciclo"] == 1
    assert (await client.get(f"{RUTA}/alertas", headers=residente)).status_code == 403
    assert (await client.get(f"{RUTA}/alertas?estado=ATENDIDA", headers=junta)).json() == []
    assert (await client.get(f"{RUTA}/alertas?estado=NOPE", headers=junta)).status_code == 422
    otro = await otro_condominio(base)
    assert (
        await client.get(f"{RUTA}/alertas", headers=junta, params={"condominio_id": str(otro)})
    ).status_code == 403
    superadmin = await login(client)
    vacio = await client.get(
        f"{RUTA}/alertas", headers=superadmin, params={"condominio_id": str(otro)}
    )
    assert vacio.status_code == 200 and vacio.json() == []


async def test_api_atender_es_idempotente_y_audita(api_usuarios):
    client, base = api_usuarios
    nid, junta = await encolar(client, base, "ana+rebote@ejemplo.test")
    assert await procesar_uno(base.sessions, ahora=datetime.now(UTC))
    [alerta] = await alertas(base, nid)
    ruta = f"{RUTA}/alertas/{alerta.id}/atender"
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    residente = await login(client, "inquilino504@villabonita3.pe", "Inquilino123!")
    assert (await client.post(ruta, headers=auditor)).status_code == 403
    assert (await client.post(ruta, headers=residente)).status_code == 403
    assert (await alertas(base, nid))[0].atendida_en is None
    falsa = f"{RUTA}/alertas/{UUID(int=1)}/atender"
    r404 = await client.post(falsa, headers=junta)
    assert r404.status_code == 404 and r404.json()["error_code"] == "ALERTA_NO_HALLADA"

    primera = await client.post(ruta, headers=junta)
    assert primera.status_code == 200, primera.text
    assert primera.json()["estado"] == "ATENDIDA"
    assert primera.json()["atendida_por"] == str(id_demo("admin@villabonita3.pe"))
    segunda = await client.post(ruta, headers=junta)
    assert segunda.status_code == 200 and segunda.json() == primera.json()
    abiertas = await client.get(f"{RUTA}/alertas", headers=junta)
    atendidas = await client.get(f"{RUTA}/alertas?estado=ATENDIDA", headers=auditor)
    assert abiertas.json() == [] and [a["id"] for a in atendidas.json()] == [str(alerta.id)]
    async with base.sessions() as db:
        n = await db.scalar(
            select(func.count()).where(
                AuditoriaLogORM.accion_ejecutada == "NOTIFICACION_ALERTA_ATENDIDA"
            )
        )
        assert n == 1


async def test_reenvio_con_contacto_corregido_atiende_la_alerta(api_usuarios):
    client, base = api_usuarios
    nid, junta = await encolar(client, base, "ana+rebote@ejemplo.test")
    assert await procesar_uno(base.sessions, ahora=datetime.now(UTC))
    async with base.sessions() as db, db.begin():
        (await db.get(Usuario, id_demo("residente102@villabonita3.pe"))).email = "ana@ejemplo.test"
    r = await client.post(
        f"{RUTA}/reenviar/{nid}", headers=junta, json={"nuevo_destinatario": "ana@ejemplo.test"}
    )
    assert r.status_code == 200 and r.json()["ciclo"] == 2
    [alerta] = await alertas(base, nid)
    assert alerta.atendida_por == id_demo("admin@villabonita3.pe") and alerta.atendida_en
    assert (await client.get(f"{RUTA}/alertas", headers=junta)).json() == []
    # Un nuevo ciclo que vuelve a fallar crea otra alerta abierta.
    async with base.sessions() as db, db.begin():
        (
            await db.get(Usuario, id_demo("residente102@villabonita3.pe"))
        ).email = "ana+rebote@ejemplo.test"
        (await db.get(Notificacion, nid)).destinatario = "ana+rebote@ejemplo.test"
    assert await procesar_uno(base.sessions, ahora=datetime.now(UTC))
    todas = await alertas(base, nid)
    assert [(a.ciclo, a.atendida_en is None) for a in todas] == [(1, False), (2, True)]


async def test_despachar_con_contexto_incompleto_no_reproduce_valores(api_usuarios):
    client, base = api_usuarios
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    r = await client.post(
        f"{RUTA}/despachar",
        headers=junta,
        json={
            "condominio_id": base.cid,
            "departamento_id": str(did("102")),
            "tipo_evento": "NOTIF_COMUNICADO_GENERAL",
            "canal": "EMAIL",
            "destinatario": "residente102@villabonita3.pe",
            "contexto": {"titulo": "secreto-xyz"},
        },
    )
    assert r.status_code == 422 and r.json()["error_code"] == "CONTEXTO_PLANTILLA_INCOMPLETO"
    assert "secreto-xyz" not in r.text
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 0
