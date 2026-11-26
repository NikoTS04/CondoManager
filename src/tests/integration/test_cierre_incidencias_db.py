import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.incidencias.models import ActualizacionIncidencia, Incidencia
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioRol
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio
from src.tests.integration.test_asignacion_incidencias_db import junta, reportar_y_asignar
from src.tests.integration.test_incidencias_db import (
    JUNTA,
    RESIDENTE,
    RUTA,
    residente,
)
from src.tests.integration.test_seguimiento_incidencias_db import avance, resolucion

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def reportar_y_resolver(client, headers):
    iid, _ = await reportar_y_asignar(client, headers)
    avanzada = await client.post(f"{RUTA}/{iid}/seguimiento", headers=headers, files=avance(2))
    assert avanzada.status_code == 201, avanzada.text
    resuelta = await client.post(
        f"{RUTA}/{iid}/resolucion", headers=headers, files=resolucion(avanzada.json()["version"])
    )
    assert resuelta.status_code == 201, resuelta.text
    return iid, resuelta.json()["version"]


async def test_confirmacion_del_residente_cierra_y_califica(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, version = await reportar_y_resolver(client, headers)
    residente_headers = await residente(client)
    confirmada = await client.post(
        f"{RUTA}/{iid}/confirmacion",
        headers=residente_headers,
        json={"version": version, "calificacion": 4, "comentario": "Quedó operativa."},
    )
    assert confirmada.status_code == 200, confirmada.text
    datos = confirmada.json()
    assert datos["estado"] == "CERRADO" and datos["calificacion"] == 4
    assert datos["cerrado_por"] == str(id_demo(RESIDENTE)) and datos["fecha_cierre"]

    async with base.sessions() as db:
        ticket = await db.get(Incidencia, iid)
        assert ticket.estado == "CERRADO" and ticket.version == version + 1
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "CIERRE_CONFORME_TICKET"
            )
        )
        assert auditoria.estado_anterior["estado_ticket"] == "RESUELTO"
        assert auditoria.estado_posterior["estado_ticket"] == "CERRADO"
        assert auditoria.actor_id == str(id_demo(RESIDENTE)) and auditoria.hash_actual
        actualizacion = await db.scalar(
            select(ActualizacionIncidencia).where(ActualizacionIncidencia.estado_nuevo == "CERRADO")
        )
        assert actualizacion.publico is True

    otra = await client.post(
        f"{RUTA}/{iid}/confirmacion",
        headers=residente_headers,
        json={"version": version, "calificacion": 4},
    )
    assert otra.status_code == 409, otra.text


async def test_reapertura_con_motivo_vuelve_a_en_proceso(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, version = await reportar_y_resolver(client, headers)
    residente_headers = await residente(client)
    reabierta = await client.post(
        f"{RUTA}/{iid}/reapertura",
        headers=residente_headers,
        json={"version": version, "motivo": "La luminaria vuelve a parpadear."},
    )
    assert reabierta.status_code == 200, reabierta.text
    datos = reabierta.json()
    assert datos["estado"] == "EN_PROCESO"
    assert datos["motivo_reapertura"] == "La luminaria vuelve a parpadear."

    historial = await client.get(f"{RUTA}/{iid}/historial", headers=headers)
    assert any(
        "La luminaria vuelve a parpadear." in item["descripcion"]
        for item in historial.json()["items"]
    )
    async with base.sessions() as db:
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "REAPERTURA_TICKET_INCIDENCIA"
            )
        )
        assert auditoria.motivo == "La luminaria vuelve a parpadear."
        assert auditoria.actor_id == str(id_demo(RESIDENTE))

    rechazada = await client.post(
        f"{RUTA}/{iid}/reapertura",
        headers=residente_headers,
        json={"version": version, "motivo": "Otro motivo"},
    )
    assert rechazada.status_code == 409, rechazada.text


async def test_cierre_administrativo_y_permisos(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, version = await reportar_y_resolver(client, headers)
    residente_headers = await residente(client)
    sin_motivo = await client.post(
        f"{RUTA}/{iid}/cierre-administrativo",
        headers=headers,
        json={"version": version, "motivo": "  "},
    )
    assert sin_motivo.status_code == 422, sin_motivo.text
    residente_intenta = await client.post(
        f"{RUTA}/{iid}/cierre-administrativo",
        headers=residente_headers,
        json={"version": version, "motivo": "Cerrado por Junta"},
    )
    assert residente_intenta.status_code == 403, residente_intenta.text
    calificacion_invalida = await client.post(
        f"{RUTA}/{iid}/confirmacion",
        headers=residente_headers,
        json={"version": version, "calificacion": 0},
    )
    assert calificacion_invalida.status_code == 422, calificacion_invalida.text

    cerrada = await client.post(
        f"{RUTA}/{iid}/cierre-administrativo",
        headers=headers,
        json={"version": version, "motivo": "Atención verificada por acta."},
    )
    assert cerrada.status_code == 200, cerrada.text
    assert cerrada.json()["cerrado_por"] == str(id_demo(JUNTA))
    async with base.sessions() as db:
        auditoria = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "CIERRE_ADMINISTRATIVO_TICKET"
            )
        )
        assert auditoria.motivo == "Atención verificada por acta."
        assert auditoria.actor_id == str(id_demo(JUNTA))

    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=id_demo(JUNTA), condominio_id=otro, rol="ADMIN_JUNTA"))
    ajena = await login(client, JUNTA, "Admin123!", condominio_id=str(otro))
    assert (
        await client.post(
            f"{RUTA}/{iid}/cierre-administrativo",
            headers=ajena,
            json={"version": version, "motivo": "Ajeno"},
        )
    ).status_code == 404
    otro_residente = await login(client, "moroso402@villabonita3.pe", "Moroso123!")
    assert (
        await client.post(
            f"{RUTA}/{iid}/confirmacion",
            headers=otro_residente,
            json={"version": version, "calificacion": 5},
        )
    ).status_code == 404


async def test_tras_reabrir_se_puede_resolver_y_cerrar_nuevamente(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, version = await reportar_y_resolver(client, headers)
    reabierta = await client.post(
        f"{RUTA}/{iid}/reapertura",
        headers=await residente(client),
        json={"version": version, "motivo": "No quedó bien."},
    )
    assert reabierta.status_code == 200, reabierta.text
    avanzada = await client.post(
        f"{RUTA}/{iid}/seguimiento",
        headers=headers,
        files=avance(reabierta.json()["version"], comentario="Segunda intervención"),
    )
    assert avanzada.status_code == 201, avanzada.text
    resuelta = await client.post(
        f"{RUTA}/{iid}/resolucion", headers=headers, files=resolucion(avanzada.json()["version"])
    )
    assert resuelta.status_code == 201, resuelta.text
    cerrada = await client.post(
        f"{RUTA}/{iid}/confirmacion",
        headers=await residente(client),
        json={"version": resuelta.json()["version"], "calificacion": 5},
    )
    assert cerrada.status_code == 200 and cerrada.json()["estado"] == "CERRADO"
    async with base.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "CIERRE_CONFORME_TICKET")
            )
        ) == 1
