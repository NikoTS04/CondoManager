import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.incidencias.models import AsignacionIncidencia, Incidencia
from src.modules.notificaciones.avisos_contrato import (
    AVISO_ASIGNACION_PROVEEDOR,
    AVISO_ASIGNACION_RESIDENTE,
)
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.modules.proveedores.models import Proveedor
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioRol
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio
from src.tests.integration.test_incidencias_db import JUNTA, RESIDENTE, RUTA, reportar, residente

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def junta(client):
    return await login(client, JUNTA, "Admin123!")


async def proveedor_directorio(base, id, email="contacto@proveedor.test", cid=CONDOMINIO_PILOTO_ID):
    async with base.sessions() as db, db.begin():
        db.add(
            Proveedor(
                id=id,
                condominio_id=cid,
                ruc="20123456789",
                razon_social="Servicios del Norte",
                rubro="MANTENIMIENTO",
                contacto_nombre="Contacto",
                contacto_telefono="999888777",
                contacto_email=email,
                creado_por=id_demo(JUNTA),
            )
        )


def asignacion_body(*, responsable=None, proveedor=None, version=1, **cambios):
    plazo = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    datos = {"version": version, "plazo": plazo}
    if responsable is not None:
        datos["responsable_usuario_id"] = str(responsable)
    if proveedor is not None:
        datos.update(proveedor)
    datos.update(cambios)
    return datos


async def reportar_y_asignar(client, junta_headers, *, proveedor=None):
    headers = await residente(client)
    creado = await reportar(client, headers)
    assert creado.status_code == 201, creado.text
    iid = creado.json()["id"]
    cuerpo = asignacion_body(
        responsable=id_demo(JUNTA) if proveedor is None else None, proveedor=proveedor
    )
    respuesta = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**junta_headers, "Idempotency-Key": str(uuid4())},
        json=cuerpo,
    )
    assert respuesta.status_code == 201, respuesta.text
    return iid, respuesta.json()


async def test_asignacion_persiste_estado_auditoria_y_aviso(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, datos = await reportar_y_asignar(client, headers)
    assert datos["estado"] == "ASIGNADO" and datos["avisos_encolados"] == 1

    async with base.sessions() as db:
        ticket = await db.get(Incidencia, iid)
        assert ticket.estado == "ASIGNADO" and ticket.version == 2
        assert ticket.responsable_usuario_id == id_demo(JUNTA)
        assert ticket.asignacion_actual_id == UUID(datos["asignacion_id"])
        asignacion = await db.get(AsignacionIncidencia, datos["asignacion_id"])
        assert asignacion.actor_id == id_demo(JUNTA)
        aviso = await db.scalar(
            select(Notificacion).where(Notificacion.tipo_evento == AVISO_ASIGNACION_RESIDENTE)
        )
        assert aviso.evento_id == asignacion.id and aviso.estado == "EN_COLA"
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "ASIGNACION_TICKET_INCIDENCIA"
            )
        )
        assert auditoria.estado_anterior["estado_ticket"] == "REGISTRADO"
        assert auditoria.estado_posterior["estado_ticket"] == "ASIGNADO"
        assert auditoria.actor_id == str(id_demo(JUNTA)) and auditoria.hash_actual

    avisos = await client.get(f"{RUTA}/{iid}/avisos", headers=headers)
    assert avisos.status_code == 200, avisos.text
    assert [(item["destinatario_tipo"], item["estado"]) for item in avisos.json()["items"]] == [
        ("RESIDENTE", "EN_COLA")
    ]


async def test_reintento_recupera_la_asignacion_y_la_reasignacion_conserva_avisos(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    residente_headers = await residente(client)
    iid = (await reportar(client, residente_headers)).json()["id"]
    cuerpo = asignacion_body(responsable=id_demo(JUNTA))
    clave = str(uuid4())
    primera = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": clave},
        json=cuerpo,
    )
    repetida = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": clave},
        json=cuerpo,
    )
    assert {primera.status_code, repetida.status_code} == {200, 201}
    assert primera.json()["asignacion_id"] == repetida.json()["asignacion_id"]
    conflicto = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": clave},
        json=asignacion_body(responsable=id_demo(JUNTA), version=1, nota="Otra nota"),
    )
    assert conflicto.status_code == 409, conflicto.text

    version = (await client.get(f"{RUTA}/{iid}", headers=headers)).json()["version"]
    reasignada = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json=asignacion_body(responsable=id_demo(JUNTA), version=version),
    )
    assert reasignada.status_code == 201, reasignada.text
    assert reasignada.json()["asignacion_id"] != primera.json()["asignacion_id"]

    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AsignacionIncidencia)) == 2
        avisos = (await db.scalars(select(Notificacion))).all()
        assert len(avisos) == 3
        assert len({aviso.evento_id for aviso in avisos}) == 3

    avisos = await client.get(f"{RUTA}/{iid}/avisos", headers=headers)
    assert len(avisos.json()["items"]) == 2


async def test_asignacion_a_proveedor_externo_no_expone_datos_del_residente(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    proveedor = uuid4()
    await proveedor_directorio(base, proveedor)
    iid, datos = await reportar_y_asignar(
        client,
        headers,
        proveedor={
            "responsable_proveedor_id": str(proveedor),
            "proveedor_nombre": "Servicios del Norte",
            "correo_proveedor": "no-usar@cliente.test",
        },
    )
    assert datos["avisos_encolados"] == 2

    async with base.sessions() as db:
        avisos = (await db.scalars(select(Notificacion))).all()
        proveedor_aviso = next(a for a in avisos if a.tipo_evento == AVISO_ASIGNACION_PROVEEDOR)
        assert proveedor_aviso.usuario_destinatario_id is None
        assert proveedor_aviso.destinatario_externo_id == proveedor
        assert proveedor_aviso.destinatario == "contacto@proveedor.test"
        assert RESIDENTE not in proveedor_aviso.cuerpo
        assert str(id_demo(RESIDENTE)) not in proveedor_aviso.cuerpo
        assert "Iluminación" in proveedor_aviso.cuerpo
        assert "MEDIA" in proveedor_aviso.cuerpo

    avisos = await client.get(f"{RUTA}/{iid}/avisos", headers=headers)
    assert {item["destinatario_tipo"] for item in avisos.json()["items"]} == {
        "RESIDENTE",
        "PROVEEDOR",
    }

    def transporte(aviso, _clave):
        return {"status": 200, "message_id": "correo-de-prueba"}

    for _ in range(3):
        assert await procesar_uno(base.sessions, transport=transporte)
    async with base.sessions() as db:
        estados = (await db.scalars(select(Notificacion.estado))).all()
        assert "ENVIADO" in estados


async def test_contacto_faltante_y_permisos_de_avisos(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    proveedor = uuid4()
    await proveedor_directorio(base, proveedor, email="")
    iid, datos = await reportar_y_asignar(
        client,
        headers,
        proveedor={
            "responsable_proveedor_id": str(proveedor),
            "proveedor_nombre": "Servicios sin correo",
        },
    )
    assert datos["avisos_encolados"] == 1
    avisos = await client.get(f"{RUTA}/{iid}/avisos", headers=headers)
    estados = {item["destinatario_tipo"]: item["estado"] for item in avisos.json()["items"]}
    assert estados["PROVEEDOR"] == "CONTACTO_FALTANTE"
    assert estados["RESIDENTE"] == "EN_COLA"

    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (await client.get(f"{RUTA}/{iid}/avisos", headers=auditor)).status_code == 200
    assert (
        await client.get(f"{RUTA}/{iid}/avisos", headers=await residente(client))
    ).status_code == 403
    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=id_demo(JUNTA), condominio_id=otro, rol="ADMIN_JUNTA"))
    ajena = await login(client, JUNTA, "Admin123!", condominio_id=str(otro))
    assert (await client.get(f"{RUTA}/{iid}/avisos", headers=ajena)).status_code == 404
    sin_responsable = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json=asignacion_body(version=2),
    )
    assert sin_responsable.status_code == 422, sin_responsable.text
    inactivo = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json=asignacion_body(responsable=uuid4(), version=2),
    )
    assert inactivo.status_code == 403, inactivo.text

    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Incidencia)) == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "ASIGNACION_TICKET_INCIDENCIA")
            )
        ) == 1


async def test_asignacion_concurrente_guarda_una_sola_decision(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    residente_headers = await residente(client)
    iid = (await reportar(client, residente_headers)).json()["id"]
    cuerpo = asignacion_body(responsable=id_demo(JUNTA))
    respuestas = await asyncio.gather(
        *(
            client.post(
                f"{RUTA}/{iid}/asignacion",
                headers={**headers, "Idempotency-Key": str(uuid4())},
                json=cuerpo,
            )
            for _ in range(2)
        )
    )
    assert {respuesta.status_code for respuesta in respuestas} == {201, 409}
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AsignacionIncidencia)) == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "ASIGNACION_TICKET_INCIDENCIA")
            )
        ) == 1


@pytest.mark.parametrize("estado", ["INEXISTENTE", "INACTIVO", "OTRO_CONDOMINIO"])
async def test_proveedor_debe_ser_activo_y_del_condominio(api_usuarios, estado):
    client, base = api_usuarios
    headers = await junta(client)
    iid = (await reportar(client, await residente(client))).json()["id"]
    pid = uuid4()
    if estado != "INEXISTENTE":
        cid = await otro_condominio(base) if estado == "OTRO_CONDOMINIO" else CONDOMINIO_PILOTO_ID
        await proveedor_directorio(base, pid, cid=cid)
        if estado == "INACTIVO":
            async with base.sessions() as db, db.begin():
                proveedor = await db.get(Proveedor, pid)
                proveedor.activo = False
    respuesta = await client.post(
        f"{RUTA}/{iid}/asignacion",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json=asignacion_body(proveedor={"responsable_proveedor_id": str(pid)}),
    )
    assert respuesta.status_code == 403, respuesta.text
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AsignacionIncidencia)) == 0
