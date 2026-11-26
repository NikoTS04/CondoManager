from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.incidencias.models import ActualizacionIncidencia, Incidencia
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioRol
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio
from src.tests.integration.test_asignacion_incidencias_db import junta, reportar_y_asignar
from src.tests.integration.test_incidencias_db import JUNTA, RUTA, residente

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


def foto():
    buffer = BytesIO()
    Image.new("RGB", (2, 2), (120, 120, 120)).save(buffer, format="PNG")
    buffer.seek(0)
    return ("evidencia.png", buffer, "image/png")


def avance(version, **cambios):
    datos = {
        "version": str(version),
        "comentario": "Diagnóstico: falla en el balastro.",
        "publico": "false",
        "repuesto": "Balastro LED",
        "monto": "45.50",
    }
    datos.update(cambios)
    return {campo: (None, valor) for campo, valor in datos.items()}


def resolucion(version, **cambios):
    datos = {
        "version": str(version),
        "descripcion": "Balastro reemplazado.",
        "publico": "true",
    }
    datos.update(cambios)
    return {campo: (None, valor) for campo, valor in datos.items()}


async def test_avance_pasa_a_en_proceso_y_guarda_costo_decimal(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, _ = await reportar_y_asignar(client, headers)
    respuesta = await client.post(
        f"{RUTA}/{iid}/seguimiento",
        headers=headers,
        files={**avance(2), "evidencia": foto()},
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["estado"] == "EN_PROCESO" and respuesta.json()["version"] == 3

    async with base.sessions() as db:
        ticket = await db.get(Incidencia, iid)
        assert ticket.estado == "EN_PROCESO"
        actualizacion = await db.scalar(select(ActualizacionIncidencia))
        assert actualizacion.actor_id == id_demo(JUNTA)
        assert actualizacion.monto == Decimal("45.50")
        assert actualizacion.publico is False
        assert actualizacion.estado_anterior == "ASIGNADO"
        assert actualizacion.estado_nuevo == "EN_PROCESO"
        assert actualizacion.tiene_evidencia
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "SEGUIMIENTO_TICKET_INCIDENCIA"
            )
        )
        assert auditoria.estado_anterior["estado_ticket"] == "ASIGNADO"
        assert auditoria.estado_posterior["estado_ticket"] == "EN_PROCESO"
        assert auditoria.actor_id == str(id_demo(JUNTA)) and auditoria.hash_actual

    historial = await client.get(f"{RUTA}/{iid}/historial", headers=headers)
    assert historial.status_code == 200, historial.text
    assert historial.json()["items"][0]["monto"] == "45.50"
    residente_headers = await residente(client)
    propia = await client.get(f"{RUTA}/{iid}/historial", headers=residente_headers)
    assert propia.json()["items"] == []


async def test_resolucion_solo_desde_en_proceso_y_con_version_vigente(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, _ = await reportar_y_asignar(client, headers)
    prematura = await client.post(
        f"{RUTA}/{iid}/resolucion",
        headers=headers,
        files=resolucion(2),
    )
    assert prematura.status_code == 409, prematura.text

    avanzada = await client.post(f"{RUTA}/{iid}/seguimiento", headers=headers, files=avance(2))
    assert avanzada.status_code == 201, avanzada.text
    version = avanzada.json()["version"]
    resuelta = await client.post(
        f"{RUTA}/{iid}/resolucion",
        headers=headers,
        files=resolucion(version),
    )
    assert resuelta.status_code == 201, resuelta.text
    assert resuelta.json()["estado"] == "RESUELTO"
    repetida = await client.post(
        f"{RUTA}/{iid}/resolucion",
        headers=headers,
        files=resolucion(resuelta.json()["version"], descripcion="Otra resolución"),
    )
    assert repetida.status_code == 409, repetida.text

    async with base.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "RESOLUCION_TICKET_INCIDENCIA")
            )
        ) == 1
        assert (await db.get(Incidencia, iid)).estado == "RESUELTO"


async def test_permisos_y_evidencia_privada_del_historial(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, _ = await reportar_y_asignar(client, headers)
    publico = await client.post(
        f"{RUTA}/{iid}/seguimiento",
        headers=headers,
        files={**avance(2, publico="true"), "evidencia": foto()},
    )
    assert publico.status_code == 201, publico.text
    privado = await client.post(
        f"{RUTA}/{iid}/seguimiento",
        headers=headers,
        files={**avance(3, publico="false"), "evidencia": foto()},
    )
    assert privado.status_code == 201, privado.text

    async with base.sessions() as db:
        actualizaciones = (
            await db.scalars(
                select(ActualizacionIncidencia).order_by(ActualizacionIncidencia.creado_en)
            )
        ).all()
        publica, privada = actualizaciones[0], actualizaciones[1]

    residente_headers = await residente(client)
    assert (
        await client.post(f"{RUTA}/{iid}/seguimiento", headers=residente_headers, files=avance(4))
    ).status_code == 403
    assert (
        await client.post(
            f"{RUTA}/{iid}/resolucion", headers=residente_headers, files=resolucion(4)
        )
    ).status_code == 403
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (await client.get(f"{RUTA}/{iid}/historial", headers=auditor)).status_code == 200

    propia = await client.get(f"{RUTA}/{iid}/historial", headers=residente_headers)
    assert [item["id"] for item in propia.json()["items"]] == [str(publica.id)]
    assert (
        await client.get(
            f"{RUTA}/{iid}/actualizaciones/{publica.id}/evidencia", headers=residente_headers
        )
    ).status_code == 200
    assert (
        await client.get(
            f"{RUTA}/{iid}/actualizaciones/{privada.id}/evidencia", headers=residente_headers
        )
    ).status_code == 404

    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=id_demo(JUNTA), condominio_id=otro, rol="ADMIN_JUNTA"))
    ajena = await login(client, JUNTA, "Admin123!", condominio_id=str(otro))
    assert (await client.get(f"{RUTA}/{iid}/historial", headers=ajena)).status_code == 404
    assert (
        await client.get(f"{RUTA}/{iid}/actualizaciones/{publica.id}/evidencia", headers=ajena)
    ).status_code == 404


async def test_evidencia_invalida_conserva_el_avance(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, _ = await reportar_y_asignar(client, headers)
    archivo = ("falso.png", BytesIO(b"no-es-una-imagen"), "image/png")
    respuesta = await client.post(
        f"{RUTA}/{iid}/seguimiento",
        headers=headers,
        files={**avance(2), "evidencia": archivo},
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.headers.get("x-advertencia-evidencia")
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ActualizacionIncidencia)) == 1
        actualizacion = await db.scalar(select(ActualizacionIncidencia))
        assert not actualizacion.tiene_evidencia
