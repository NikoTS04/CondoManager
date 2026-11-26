import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.core import jobs
from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.modules.excepciones.jobs import tomar_reintento
from src.modules.excepciones.models import ResolucionExcepcion
from src.modules.excepciones.service import AUDITORIA_RESOLUCION
from src.modules.notificaciones import recordatorios, worker
from src.modules.notificaciones.alertas import ciclo_job, crear_alerta_job
from src.modules.notificaciones.models import AlertaNotificacion, Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioRol
from src.tests.integration.test_alertas_notificaciones_db import alertas, encolar
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
RUTA = "/api/v1/excepciones"
JUNTA = "admin@villabonita3.pe"
RESIDENTE = "residente102@villabonita3.pe"
CORREO_FALLIDO = "ana+rebote@ejemplo.test"


async def fallo(client, base, monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    aviso, junta = await encolar(client, base, CORREO_FALLIDO)
    assert await procesar_uno(base.sessions)
    [alerta] = await alertas(base, aviso)
    return aviso, f"{RUTA}/{alerta.id}", junta


def con_clave(headers):
    return {**headers, "Idempotency-Key": str(uuid4())}


async def test_bandeja_y_resolucion_se_aislan_por_rol_y_condominio(api_usuarios, monkeypatch):
    client, base = api_usuarios
    _, ruta, junta = await fallo(client, base, monkeypatch)
    propia = await client.get(ruta, headers=junta)
    assert propia.status_code == 200, propia.text
    assert propia.json()["evidencia"]["estado_operacion"] == "FALLIDO_PERMANENTE"
    assert "@ejemplo.test" not in propia.text
    listado = await client.get(RUTA, headers=junta)
    assert listado.json()["items"][0]["id"] == propia.json()["id"]

    superadmin = await login(client)
    assert (await client.get(RUTA, headers=superadmin)).json()["items"] == []
    assert (await client.get(ruta, headers=superadmin)).status_code == 404
    residente = await login(client, CORREO_FALLIDO, "Residente123!")
    assert (await client.get(RUTA, headers=residente)).status_code == 403
    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=id_demo(JUNTA), condominio_id=otro, rol="ADMIN_JUNTA"))
    junta_ajena = await login(client, JUNTA, "Admin123!", condominio_id=str(otro))
    assert (await client.get(RUTA, headers=junta_ajena)).json()["items"] == []
    assert (await client.get(ruta, headers=junta_ajena)).status_code == 404
    respuesta = await client.post(
        f"{ruta}/resoluciones",
        headers=con_clave(junta_ajena),
        json={"accion": "CERRAR_CON_MOTIVO", "motivo": "Ya se avisó por teléfono."},
    )
    assert respuesta.status_code == 404


async def test_cerrar_exige_motivo_y_persiste_el_efecto_y_actor(api_usuarios, monkeypatch):
    client, base = api_usuarios
    aviso_id, ruta, junta = await fallo(client, base, monkeypatch)
    headers = con_clave(junta)
    datos = {"accion": "CERRAR_CON_MOTIVO", "motivo": " "}
    assert (
        await client.post(f"{ruta}/resoluciones", headers=headers, json=datos)
    ).status_code == 422
    datos["motivo"] = "Ya se informó por teléfono."
    cierre = await client.post(f"{ruta}/resoluciones", headers=headers, json=datos)
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["actor_id"] == str(id_demo(JUNTA))
    assert cierre.json()["motivo"] == datos["motivo"]
    assert cierre.json()["estado"] == "RESUELTA"
    assert cierre.json()["efecto"]["estado_operacion"] == "OMITIDO"
    detalle = (await client.get(ruta, headers=junta)).json()
    assert detalle["historial"] == [cierre.json()] and detalle["acciones_permitidas"] == []
    async with base.sessions() as db:
        assert (await db.get(Notificacion, aviso_id)).estado == "OMITIDO"


async def test_reenvio_valida_contacto_e_idempotencia_y_refleja_resultado(
    api_usuarios, monkeypatch
):
    client, base = api_usuarios
    aviso_id, ruta, junta = await fallo(client, base, monkeypatch)
    correo = "ana-corregido@ejemplo.test"
    datos = {
        "accion": "REENVIAR_CORREO",
        "motivo": "El correo anterior rebotó.",
        "nuevo_destinatario": correo,
    }
    headers = con_clave(junta)
    denegado = await client.post(f"{ruta}/resoluciones", headers=headers, json=datos)
    assert denegado.status_code == 422, denegado.text
    async with base.sessions() as db, db.begin():
        (await db.get(Usuario, id_demo(RESIDENTE))).email = correo
    a, b = await asyncio.gather(
        client.post(f"{ruta}/resoluciones", headers=headers, json=datos),
        client.post(f"{ruta}/resoluciones", headers=headers, json=datos),
    )
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json() == b.json() and a.json()["estado"] == "EN_PROCESO"
    assert (await client.get(ruta, headers=junta)).json()["estado"] == "EN_PROCESO"
    conflicto = await client.post(
        f"{ruta}/resoluciones",
        headers=headers,
        json={**datos, "motivo": "Otro motivo"},
    )
    assert conflicto.status_code == 409

    assert await procesar_uno(base.sessions)
    detalle = (await client.get(ruta, headers=junta)).json()
    assert detalle["estado"] == "RESUELTA" and detalle["evidencia"]["estado_operacion"] == "ENVIADO"
    async with base.sessions() as db:
        aviso = await db.get(Notificacion, aviso_id)
        assert aviso.ciclo == 2 and aviso.intentos == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == AUDITORIA_RESOLUCION)
            )
            == 1
        )


async def alerta_global(base, *, dias=0, nombre="notificaciones"):
    ahora = datetime.now(UTC) - timedelta(days=dias)
    async with base.sessions() as db, db.begin():
        assert await crear_alerta_job(db, nombre, 1, 1, ahora, "ref-demo-job")
        id = await db.scalar(
            select(AlertaNotificacion.id).where(
                AlertaNotificacion.origen_tipo == "JOB",
                AlertaNotificacion.origen_id == nombre,
                AlertaNotificacion.ciclo == ciclo_job(ahora),
            )
        )
    return f"{RUTA}/{id}"


def preparar_job(base, monkeypatch):
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    monkeypatch.setattr(jobs, "AsyncSessionLocal", base.sessions)
    monkeypatch.setattr(jobs, "recuperar_eventos", AsyncMock())
    monkeypatch.setattr(worker, "recuperar_inciertos", AsyncMock())
    monkeypatch.setattr(recordatorios, "generar_recordatorios", AsyncMock())
    enviar = AsyncMock(side_effect=[True, False])
    monkeypatch.setattr(worker, "procesar_uno", enviar)
    return enviar


async def test_solo_superadmin_gestiona_jobs_globales_y_deja_solicitud_en_historial(api_usuarios):
    client, base = api_usuarios
    ruta = await alerta_global(base, nombre="diario")
    admin = await login(client)
    junta = await login(client, JUNTA, "Admin123!")
    assert (await client.get(RUTA, headers=junta)).json()["items"] == []
    assert (await client.get(ruta, headers=junta)).status_code == 404
    assert (await client.get(RUTA, headers=admin)).json()["items"][0]["origen"] == "JOB"

    datos = {
        "accion": "SOLICITAR_INFORMACION",
        "motivo": "Falta confirmar la causa de la interrupción.",
        "responsable": "Equipo de operación",
    }
    assert (
        await client.post(f"{ruta}/resoluciones", headers=con_clave(junta), json=datos)
    ).status_code == 404
    pendiente = await client.post(f"{ruta}/resoluciones", headers=con_clave(admin), json=datos)
    assert pendiente.status_code == 200, pendiente.text
    detalle = (await client.get(ruta, headers=admin)).json()
    assert detalle["estado"] == "PENDIENTE_INFORMACION"
    assert detalle["historial"] == [pendiente.json()]
    assert detalle["historial"][0]["motivo"] == datos["motivo"]
    assert detalle["evidencia"]["referencia_correlacion"] == "ref-demo-job"
    assert detalle["historial"][0]["efecto"]["responsable"] == datos["responsable"]
    cierre = await client.post(
        f"{ruta}/resoluciones",
        headers=con_clave(admin),
        json={"accion": "CERRAR_CON_MOTIVO", "motivo": "El equipo confirmó el resultado."},
    )
    assert cierre.status_code == 200 and cierre.json()["estado"] == "RESUELTA"


async def test_reintento_job_se_ejecuta_una_sola_vez_y_actualiza_el_caso(api_usuarios, monkeypatch):
    client, base = api_usuarios
    ruta, otra_ruta = await alerta_global(base), await alerta_global(base, dias=1)
    enviar = preparar_job(base, monkeypatch)
    admin = await login(client)
    headers = con_clave(admin)
    datos = {"accion": "REINTENTAR_JOB", "motivo": "Se recuperó la conexión."}
    a, b = await asyncio.gather(
        client.post(f"{ruta}/resoluciones", headers=headers, json=datos),
        client.post(f"{ruta}/resoluciones", headers=headers, json=datos),
    )
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json() == b.json() and a.json()["efecto"]["estado_operacion"] == "EN_COLA"
    conflictiva = await client.post(
        f"{otra_ruta}/resoluciones", headers=con_clave(admin), json=datos
    )
    assert (
        conflictiva.status_code == 409
        and conflictiva.json()["error_code"] == "JOB_REINTENTO_ACTIVO"
    )
    assert (await jobs.ejecutar_notificaciones())["procesadas"] == 1
    assert enviar.await_count == 2
    detalle = (await client.get(ruta, headers=admin)).json()
    assert detalle["estado"] == "RESUELTA"
    assert detalle["evidencia"]["intento_id"] == a.json()["efecto"]["intento_id"]
    assert detalle["evidencia"]["estado_operacion"] == "COMPLETADO"
    assert len(detalle["historial"]) == 1


async def test_job_interrumpido_conserva_referencia_y_resultado_incierto(api_usuarios, monkeypatch):
    client, base = api_usuarios
    ruta = await alerta_global(base)
    preparar_job(base, monkeypatch)
    admin = await login(client)
    datos = {"accion": "REINTENTAR_JOB", "motivo": "Se solicitó un nuevo intento."}
    r = await client.post(f"{ruta}/resoluciones", headers=con_clave(admin), json=datos)
    assert r.status_code == 200, r.text
    id = await tomar_reintento(base.sessions)
    assert str(id) == r.json()["efecto"]["intento_id"]
    await jobs.ejecutar_notificaciones()
    detalle = (await client.get(ruta, headers=admin)).json()
    assert detalle["estado"] == "FALLIDA"
    assert detalle["evidencia"]["intento_id"] == str(id)
    assert detalle["evidencia"]["estado_operacion"] == "INCIERTO"
    assert "REINTENTAR_JOB" not in detalle["acciones_permitidas"]
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ResolucionExcepcion)) == 1
