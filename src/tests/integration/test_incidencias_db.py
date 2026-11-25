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
from src.modules.usuarios.models import UsuarioRol
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
