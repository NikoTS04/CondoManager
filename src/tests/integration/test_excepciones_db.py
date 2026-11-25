import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.modules.excepciones.service import AUDITORIA_RESOLUCION
from src.modules.notificaciones.models import Notificacion
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
