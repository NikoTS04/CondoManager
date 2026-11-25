import asyncio
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.incidencias.models import Incidencia
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.repository import AVISO_INCIDENCIA
from src.modules.notificaciones.worker import procesar_uno
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioDepartamento, UsuarioRol
from src.modules.usuarios.piloto import vinculo_piloto
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]

RUTA = "/api/v1/incidencias"
RESIDENTE = "residente102@villabonita3.pe"
JUNTA = "admin@villabonita3.pe"


async def reportar(client, headers, *, archivo=None, **cambios):
    datos = {
        "departamento_id": str(vinculo_piloto("102", "PROPIETARIO_TITULAR")["departamento_id"]),
        "ubicacion": "Torre B, pasillo del piso 4",
        "categoria": "Iluminación",
        "descripcion": "La luminaria dejó de funcionar.",
        "urgencia": "MEDIA",
        **cambios,
    }
    multipart = {campo: (None, valor) for campo, valor in datos.items()}
    if archivo:
        multipart["evidencia"] = archivo
    return await client.post(RUTA, headers=headers, files=multipart)


async def residente(client, **extra):
    sesion = await login(client, RESIDENTE, "Residente123!", **extra)
    return {**sesion, "Idempotency-Key": str(uuid4())}


async def test_registro_persiste_auditoria_y_aviso_para_junta(api_usuarios, monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)
    client, base = api_usuarios
    headers = await residente(client)
    incompleto = await reportar(client, headers, ubicacion="")
    assert incompleto.status_code == 422, incompleto.text
    async with base.sessions() as db:
        assert await db.scalar(select(Incidencia.id)) is None
        assert await db.scalar(select(Notificacion.id)) is None
    respuesta = await reportar(client, headers)
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["estado"] == "REGISTRADO"
    assert datos["tiene_evidencia"] is False
    assert datos["advertencia_evidencia"] is None
    iid = UUID(datos["id"])

    async with base.sessions() as db:
        assert (await db.get(Incidencia, iid)).reportante_id == id_demo(RESIDENTE)
        avisos = (await db.scalars(select(Notificacion))).all()
        assert [(a.tipo_evento, a.destinatario, a.evento_id, a.estado) for a in avisos] == [
            (AVISO_INCIDENCIA, JUNTA, iid, "EN_COLA")
        ]
        assert f"/incidencias/{iid}" in avisos[0].cuerpo
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "CREACION_TICKET_INCIDENCIA"
            )
        )
        assert auditoria.estado_posterior["incidencia_id"] == datos["id"]
        assert auditoria.estado_posterior["avisos_encolados"] == 1

    def transporte_simulado(aviso, _clave):
        assert aviso.destinatario == JUNTA
        return {"status": 200, "message_id": "correo-de-prueba"}

    assert await procesar_uno(base.sessions, transport=transporte_simulado)
    async with base.sessions() as db:
        assert await db.scalar(select(Notificacion.estado)) == "ENVIADO"


async def test_reintento_concurrente_conserva_id_y_un_aviso(api_usuarios):
    client, base = api_usuarios
    headers = await residente(client)
    primera, segunda = await asyncio.gather(reportar(client, headers), reportar(client, headers))
    assert {primera.status_code, segunda.status_code} == {200, 201}
    assert primera.json() == segunda.json()
    conflicto = await reportar(client, headers, ubicacion="Otra ubicación")
    assert conflicto.status_code == 409, conflicto.text
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Incidencia)) == 1
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1


async def test_detalle_y_foto_se_restringen_al_condominio(api_usuarios):
    client, base = api_usuarios
    imagen = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(imagen, "PNG")
    headers = await residente(client)
    creado = await reportar(client, headers, archivo=("foto.png", imagen.getvalue(), "image/png"))
    assert creado.status_code == 201, creado.text
    assert creado.json()["tiene_evidencia"] is True
    ruta = f"{RUTA}/{creado.json()['id']}"

    junta = await login(client, JUNTA, "Admin123!")
    assert (await client.get(ruta, headers=junta)).status_code == 200
    foto = await client.get(f"{ruta}/evidencia", headers=junta)
    assert foto.status_code == 200 and foto.content == imagen.getvalue()
    assert foto.headers["cache-control"] == "private, no-store"

    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=id_demo(RESIDENTE), condominio_id=otro, rol="RESIDENTE"))
    sesion_otro = await residente(client, condominio_id=str(otro))
    for recurso in (ruta, f"{ruta}/evidencia"):
        assert (await client.get(recurso, headers=sesion_otro)).status_code == 404
    listado = await client.get(f"{RUTA}/mis-reportes", headers=sesion_otro)
    assert listado.json() == {"items": [], "hay_mas": False}


async def test_foto_corrupta_conserva_el_reporte(api_usuarios):
    client, _ = api_usuarios
    headers = await residente(client)
    archivo = ("foto.png", b"\x89PNG\r\n\x1a\ncorrupta", "image/png")
    creado = await reportar(client, headers, archivo=archivo)
    assert creado.status_code == 201, creado.text
    registro = creado.json()
    assert registro["tiene_evidencia"] is False and registro["advertencia_evidencia"]
    ruta = f"{RUTA}/{registro['id']}"
    detalle = await client.get(ruta, headers=headers)
    assert detalle.status_code == 200 and detalle.json()["descripcion"] == registro["descripcion"]
    assert (await client.get(f"{ruta}/evidencia", headers=headers)).status_code == 404


def clasificacion(categoria="Electricidad", prioridad="URGENTE", version=1):
    return {
        "accion": "CLASIFICAR",
        "categoria": categoria,
        "prioridad": prioridad,
        "version": version,
    }


async def test_bandeja_prioriza_los_urgentes_segun_revision_y_conserva_original(api_usuarios):
    client, base = api_usuarios
    headers = await residente(client)
    original_urgente = (await reportar(client, headers, urgencia="URGENTE")).json()
    otro = (
        await reportar(
            client,
            {**headers, "Idempotency-Key": str(uuid4())},
            ubicacion="Torre A, entrada",
        )
    ).json()
    junta = await login(client, JUNTA, "Admin123!")

    inicial = await client.get(RUTA, headers=junta, params={"limit": 1})
    assert inicial.status_code == 200, inicial.text
    assert inicial.json()["items"][0]["id"] == original_urgente["id"]
    assert inicial.json()["hay_mas"] is True
    cambio = await client.patch(
        f"{RUTA}/{otro['id']}/revision",
        headers=junta,
        json=clasificacion(),
    )
    baja = await client.patch(
        f"{RUTA}/{original_urgente['id']}/revision",
        headers=junta,
        json=clasificacion(prioridad="BAJA"),
    )
    assert cambio.status_code == baja.status_code == 200, (cambio.text, baja.text)
    actual = cambio.json()
    assert actual["categoria"] == "Iluminación" and actual["categoria_confirmada"] == "Electricidad"
    assert actual["urgencia"] == "MEDIA" and actual["prioridad"] == "URGENTE"
    assert actual["estado"] == "REGISTRADO" and actual["version"] == 2
    bandeja = await client.get(RUTA, headers=junta)
    assert [item["id"] for item in bandeja.json()["items"]] == [otro["id"], original_urgente["id"]]
    async with base.sessions() as db:
        fila = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "CLASIFICACION_TICKET_INCIDENCIA",
                AuditoriaLogORM.estado_posterior["incidencia_id"].astext == otro["id"],
            )
        )
        assert fila.actor_id == str(id_demo(JUNTA))
        assert fila.estado_anterior["prioridad"] is None
        assert fila.estado_posterior["prioridad"] == "URGENTE"


async def test_rechazo_es_terminal_y_el_residente_ve_el_motivo(api_usuarios):
    client, base = api_usuarios
    headers = await residente(client)
    creado = await reportar(client, headers)
    ruta = f"{RUTA}/{creado.json()['id']}"
    junta = await login(client, JUNTA, "Admin123!")
    decision = {"accion": "RECHAZAR", "version": 1}
    incompleto = await client.patch(
        f"{ruta}/revision", headers=junta, json={**decision, "motivo": " "}
    )
    assert incompleto.status_code == 422, incompleto.text
    motivo = "El desperfecto corresponde a un predio vecino."
    rechazo = await client.patch(
        f"{ruta}/revision", headers=junta, json={**decision, "motivo": motivo}
    )
    assert rechazo.status_code == 200, rechazo.text
    detalle = await client.get(ruta, headers=headers)
    assert detalle.json()["estado"] == "RECHAZADO"
    assert detalle.json()["motivo_rechazo"] == motivo
    listado = await client.get(f"{RUTA}/mis-reportes", headers=headers)
    assert listado.json()["items"] == [detalle.json()]
    assert (await client.get(f"{RUTA}/mis-reportes", headers=junta)).status_code == 403
    revision = await client.patch(
        f"{ruta}/revision",
        headers=junta,
        json=clasificacion(version=detalle.json()["version"]),
    )
    assert revision.status_code == 409 and revision.json()["error_code"] == "INCIDENCIA_NO_EDITABLE"
    reintento = await reportar(client, headers)
    assert reintento.status_code == 200 and reintento.json() == creado.json()
    async with base.sessions() as db:
        fila = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "RECHAZO_TICKET_INCIDENCIA"
            )
        )
        assert fila.motivo == motivo and fila.estado_posterior["estado_ticket"] == "RECHAZADO"


async def test_solo_junta_del_condominio_puede_listar_y_revisar(api_usuarios):
    client, base = api_usuarios
    headers = await residente(client)
    creado = await reportar(client, headers)
    ruta = f"{RUTA}/{creado.json()['id']}"
    assert (await client.get(RUTA, headers=headers)).status_code == 403
    assert (
        await client.patch(f"{ruta}/revision", headers=headers, json=clasificacion())
    ).status_code == 403

    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=id_demo(JUNTA), condominio_id=otro, rol="ADMIN_JUNTA"))
    junta_ajena = await login(client, JUNTA, "Admin123!", condominio_id=str(otro))
    assert (await client.get(RUTA, headers=junta_ajena)).json() == {"items": [], "hay_mas": False}
    assert (
        await client.patch(f"{ruta}/revision", headers=junta_ajena, json=clasificacion())
    ).status_code == 404


async def test_dos_revisiones_de_la_misma_version_guardan_una_decision(api_usuarios):
    client, base = api_usuarios
    creado = await reportar(client, await residente(client))
    ruta = f"{RUTA}/{creado.json()['id']}"
    junta = await login(client, JUNTA, "Admin123!")
    respuestas = await asyncio.gather(
        client.patch(f"{ruta}/revision", headers=junta, json=clasificacion()),
        client.patch(
            f"{ruta}/revision", headers=junta, json=clasificacion("Infraestructura", "ALTA")
        ),
    )
    assert {respuesta.status_code for respuesta in respuestas} == {200, 409}
    ganadora = next(r.json() for r in respuestas if r.status_code == 200)
    conflicto = next(r.json() for r in respuestas if r.status_code == 409)
    assert conflicto["error_code"] == "VERSION_DESACTUALIZADA"
    assert (await client.get(ruta, headers=junta)).json() == ganadora
    async with base.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "CLASIFICACION_TICKET_INCIDENCIA")
            )
            == 1
        )


async def test_mis_reportes_solo_lista_al_autor_incluso_en_una_unidad_compartida(api_usuarios):
    client, base = api_usuarios
    ruta = f"{RUTA}/mis-reportes"
    propios = await residente(client)
    primero = await reportar(client, propios)
    assert primero.status_code == 201, primero.text

    vecino = "moroso402@villabonita3.pe"
    async with base.sessions() as db, db.begin():
        db.add(
            UsuarioDepartamento(
                usuario_id=id_demo(vecino),
                departamento_id=UUID(primero.json()["departamento_id"]),
                tipo_relacion="COPROPIETARIO",
            )
        )
    sesion_vecino = await login(client, vecino, "Moroso123!")
    ajeno = await reportar(client, {**sesion_vecino, "Idempotency-Key": str(uuid4())})
    assert ajeno.status_code == 201, ajeno.text

    segundo = await reportar(client, {**propios, "Idempotency-Key": str(uuid4())})
    assert segundo.status_code == 201, segundo.text
    pagina = await client.get(ruta, headers=propios, params={"limit": 1})
    assert pagina.status_code == 200, pagina.text
    assert pagina.headers["cache-control"] == "private, no-store"
    assert [item["id"] for item in pagina.json()["items"]] == [segundo.json()["id"]]
    assert pagina.json()["hay_mas"] is True

    otra_pagina = await client.get(ruta, headers=propios, params={"limit": 1, "offset": 1})
    assert [item["id"] for item in otra_pagina.json()["items"]] == [primero.json()["id"]]
    assert otra_pagina.json()["hay_mas"] is False
    reportes_vecino = await client.get(ruta, headers=sesion_vecino)
    assert [item["id"] for item in reportes_vecino.json()["items"]] == [ajeno.json()["id"]]
