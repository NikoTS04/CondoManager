from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.core.reintentos_job import JOBES_REINTENTABLES
from src.modules.excepciones.models import EvidenciaExcepcion, Excepcion, ResolucionExcepcion
from src.modules.notificaciones.alertas import crear_alerta_job
from src.modules.notificaciones.models import AlertaNotificacion, EstadoJobNotificaciones
from src.tests.integration.test_alta_usuarios_db import login

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]

SUPERADMIN = "superadmin@condomanager.pe"
SENTINELA = "3709ed64-791a-5cd8-99c7-142ab3ee590c"
RUTA = "/api/v1/excepciones"


async def crear_job(base, nombre, referencia):
    async with base.sessions() as db, db.begin():
        db.add(
            EstadoJobNotificaciones(nombre=nombre, inicio=datetime.now(UTC), estado="INCOMPLETO")
        )
        await crear_alerta_job(db, nombre, 1, 1, referencia_correlacion=referencia)


async def test_alerta_de_job_es_global_y_se_persiste_con_evidencia(api_usuarios):
    client, base = api_usuarios
    await crear_job(base, "diario", "corr-diario")
    superadmin = await login(client, SUPERADMIN, "SuperAdmin123!")

    respuesta = await client.get(RUTA, headers=superadmin)
    assert respuesta.status_code == 200, respuesta.text
    caso = next(item for item in respuesta.json()["items"] if item["origen"] == "JOB")
    assert caso["operacion_id"] == "diario" and caso["estado"] == "ABIERTA"

    detalle = await client.get(f"{RUTA}/{caso['id']}", headers=superadmin)
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["evidencia"]["origen"] == "JOB"
    assert detalle.json()["evidencia"]["referencia_correlacion"] == "corr-diario"
    assert detalle.json()["acciones_permitidas"] == ["CERRAR_CON_MOTIVO"]

    async with base.sessions() as db:
        persistida = await db.scalar(select(Excepcion).where(Excepcion.origen == "JOB"))
        assert persistida.operacion_id == "diario"
        assert await db.scalar(select(func.count()).select_from(EvidenciaExcepcion)) == 1

    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    assert (await client.get(f"{RUTA}/{caso['id']}", headers=junta)).status_code == 404
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    assert (await client.get(f"{RUTA}/{caso['id']}", headers=residente)).status_code == 403


async def test_reintento_de_job_seguro_guarda_efecto_real_y_es_idempotente(api_usuarios):
    client, base = api_usuarios
    await crear_job(base, "notificaciones", "corr-notif")
    superadmin = await login(client, SUPERADMIN, "SuperAdmin123!")
    lista = await client.get(RUTA, headers=superadmin)
    caso = next(item for item in lista.json()["items"] if item["origen"] == "JOB")
    assert (
        "REINTENTAR_JOB"
        in (await client.get(f"{RUTA}/{caso['id']}", headers=superadmin)).json()[
            "acciones_permitidas"
        ]
    )

    solicitud = {"accion": "REINTENTAR_JOB", "motivo": "Reintento controlado."}
    clave = str(uuid4())
    primera = await client.post(
        f"{RUTA}/{caso['id']}/resoluciones",
        headers={**superadmin, "Idempotency-Key": clave},
        json=solicitud,
    )
    assert primera.status_code == 200, primera.text
    efecto = primera.json()["efecto"]
    assert efecto["reintentado"] is True and efecto["estado_proceso"] == "EN_CURSO"

    async with base.sessions() as db:
        registro = await db.scalar(
            select(EstadoJobNotificaciones).where(
                EstadoJobNotificaciones.nombre == "notificaciones"
            )
        )
        assert registro.estado == "EN_CURSO"
        alerta = await db.get(AlertaNotificacion, caso["id"])
        assert alerta.atendida_en is not None
        assert (await db.scalar(select(func.count()).select_from(ResolucionExcepcion))) == 1
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "EXCEPCION_JOB_RESUELTA"
            )
        )
        assert str(auditoria.condominio_id) == SENTINELA
        assert auditoria.estado_posterior["efecto"]["reintentado"] is True

    repetida = await client.post(
        f"{RUTA}/{caso['id']}/resoluciones",
        headers={**superadmin, "Idempotency-Key": clave},
        json=solicitud,
    )
    assert repetida.status_code == 200 and repetida.json() == primera.json()
    otra = await client.post(
        f"{RUTA}/{caso['id']}/resoluciones",
        headers={**superadmin, "Idempotency-Key": str(uuid4())},
        json={"accion": "REINTENTAR_JOB", "motivo": "Otro motivo"},
    )
    assert otra.status_code == 409, otra.text
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ResolucionExcepcion)) == 1


async def test_job_no_seguro_solo_permite_cerrar_con_motivo(api_usuarios):
    client, base = api_usuarios
    await crear_job(base, "diario", "corr-diario-2")
    superadmin = await login(client, SUPERADMIN, "SuperAdmin123!")
    lista = await client.get(RUTA, headers=superadmin)
    caso = next(
        item
        for item in lista.json()["items"]
        if item["origen"] == "JOB" and item["operacion_id"] == "diario"
    )
    reintento = await client.post(
        f"{RUTA}/{caso['id']}/resoluciones",
        headers={**superadmin, "Idempotency-Key": str(uuid4())},
        json={"accion": "REINTENTAR_JOB", "motivo": "No debería permitirse."},
    )
    assert reintento.status_code == 409, reintento.text

    cierre = await client.post(
        f"{RUTA}/{caso['id']}/resoluciones",
        headers={**superadmin, "Idempotency-Key": str(uuid4())},
        json={"accion": "CERRAR_CON_MOTIVO", "motivo": "Ya se avisó por otro canal."},
    )
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["efecto"]["estado_operacion"] == "CERRADA"
    detalle = await client.get(f"{RUTA}/{caso['id']}", headers=superadmin)
    assert detalle.json()["estado"] == "RESUELTA" and detalle.json()["acciones_permitidas"] == []
    assert len(detalle.json()["historial"]) == 1
    assert "diario" not in JOBES_REINTENTABLES
