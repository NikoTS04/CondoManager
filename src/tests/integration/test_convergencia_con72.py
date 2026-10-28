"""Contrato publicado sobre respuestas reales, evidencia versionada y consumidores."""

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.main import app
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import Notificacion
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_persistencia import ArchivoVoucher, EventoPagoOutbox, RevisionPago
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.storage import VoucherStorage
from src.modules.pagos.worker import limpiar_pendientes
from src.tests.integration.test_pagos_db import imagen, login, reportar

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
CONTRATOS = Path("specs/03-contracts").resolve()
RECURSOS = [
    *CONTRATOS.joinpath("openapi").glob("*.yaml"),
    *CONTRATOS.joinpath("events/schemas").glob("*.json"),
]
REGISTRY = Registry().with_resources(
    (
        p.as_uri(),
        Resource.from_contents(yaml.safe_load(p.read_text()), default_specification=DRAFT202012),
    )
    for p in RECURSOS
)


def validar(nombre, data):
    ref = (CONTRATOS / "openapi/sprint-2.schemas.yaml").as_uri() + "#/schemas/" + nombre
    Draft202012Validator({"$ref": ref}, registry=REGISTRY, format_checker=FormatChecker()).validate(
        data
    )


def respuesta(response, estado, nombre):
    assert response.status_code == estado, response.text
    validar(nombre, response.json())
    return response.json()


async def revisar(client, junta, id, decision="OBSERVADO", motivo="Archivo ilegible", notas=None):
    return await client.post(
        f"/api/v1/pagos/{id}/conciliar",
        headers=junta,
        json={"decision": decision, "motivo_rechazo": motivo, "notas_internas": notas},
    )


async def subsanar(client, usuario, id, contenido=None, **campos):
    return await client.put(
        f"/api/v1/pagos/{id}/voucher",
        headers=usuario,
        data=campos,
        files={
            "archivo_voucher": (
                "corregido.png",
                imagen() if contenido is None else contenido,
                "image/png",
            )
        },
    )


async def test_ciclo_completo_contra_contrato_y_eventos(api_pagos):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    recibido = respuesta(await reportar(client, usuario, operacion="1"), 202, "ComprobanteRecibido")
    id = recibido["comprobante_id"]
    repetido = respuesta(
        await reportar(client, usuario, operacion="0001"), 200, "ComprobanteRecibido"
    )
    assert repetido["codigo"] == "VOUCHER_EN_EVALUACION" and repetido["comprobante_id"] == id
    observado = respuesta(
        await revisar(client, junta, id, notas="SOLO-ADMIN"), 200, "ResultadoRevision"
    )
    assert observado["motivo_rechazo"] == "Archivo ilegible" and "SOLO-ADMIN" not in json.dumps(
        observado
    )
    respuesta(await revisar(client, junta, id, notas="SOLO-ADMIN"), 200, "ResultadoRevision")
    respuesta(await revisar(client, junta, id, decision="APROBADO", motivo=None), 409, "Error")
    duplicado = respuesta(await reportar(client, usuario, operacion="1"), 409, "Error")
    assert duplicado["error_code"] == "VOUCHER_REQUIERE_SUBSANACION"
    nueva = respuesta(await subsanar(client, usuario, id), 202, "ComprobanteRecibido")
    assert (
        nueva["comprobante_id"] == id and nueva["idempotency_hash"] == recibido["idempotency_hash"]
    )
    respuesta(await client.get(f"/api/v1/pagos/{id}/resultado", headers=usuario), 404, "Error")
    respuesta(await subsanar(client, usuario, id), 409, "Error")
    aprobado = respuesta(
        await revisar(client, junta, id, decision="APROBADO", motivo=None), 200, "ResultadoRevision"
    )
    assert aprobado["monto_imputado"] == "170.00" and aprobado["motivo_rechazo"] is None
    assert (
        respuesta(
            await revisar(client, junta, id, decision="APROBADO", motivo=None),
            200,
            "ResultadoRevision",
        )
        == aprobado
    )
    listado = await client.get("/api/v1/pagos/comprobantes", headers=usuario)
    assert listado.status_code == 200
    for c in listado.json():
        validar("Comprobante", c)
    assert listado.json()[0]["estado"] == "APROBADO"
    privado = await client.get(listado.json()[0]["url_voucher"], headers=usuario)
    assert privado.content == imagen() and privado.headers["cache-control"] == "no-store"
    assert privado.headers["content-type"] == "image/png"
    historial = await client.get(f"/api/v1/pagos/{id}/evidencias", headers=usuario)
    assert historial.status_code == 200 and len(historial.json()) == 2
    assert all(set(e) == {"evidencia_id", "content_type", "creado_en"} for e in historial.json())
    for e in historial.json():
        vista = await client.get(
            f"/api/v1/pagos/{id}/voucher",
            params={"evidencia_id": e["evidencia_id"], "disposicion": "inline"},
            headers=usuario,
        )
        assert vista.status_code == 200 and vista.content == imagen()
        assert vista.headers["content-disposition"].startswith("inline")
    inexistente = await client.get(
        f"/api/v1/pagos/{id}/voucher?evidencia_id={uuid4()}", headers=usuario
    )
    assert inexistente.status_code == 404
    async with base.sessions() as db:
        archivos = list(await db.scalars(select(ArchivoVoucher)))
        revisiones = list(await db.scalars(select(RevisionPago)))
        eventos = list(await db.scalars(select(EventoPagoOutbox)))
        assert len(archivos) == 2 and len(revisiones) == 2 and len(eventos) == 4
        assert len({r.archivo_nombre for r in revisiones}) == 2
        assert revisiones[0].notas_internas == "SOLO-ADMIN"
        assert await db.scalar(select(func.count()).select_from(ImputacionPago)) == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "COMPROBANTE_SUBSANADO")
            )
            == 1
        )
    await limpiar_pendientes(base.sessions)
    assert all(VoucherStorage().ruta(a.nombre).exists() for a in archivos)
    for evento in eventos:
        archivo = {
            "PagoReportadoEvent": "pago-reportado.v1.schema.json",
            "PagoConciliadoEvent": "pago-conciliado.v1.schema.json",
            "PagoRevisadoEvent": "pago-revisado.v1.schema.json",
        }[evento.payload["event_type"]]
        Draft202012Validator(
            {"$ref": (CONTRATOS / "events/schemas" / archivo).as_uri()},
            registry=REGISTRY,
            format_checker=FormatChecker(),
        ).validate(evento.payload)
        assert await consumir(base.sessions, evento.payload) == 1
        assert await consumir(base.sessions, evento.payload) == 0
    logs = await client.get("/api/v1/notificaciones/logs", headers=usuario)
    assert len(logs.json()) == 4
    for log in logs.json():
        validar("Notificacion", log)
        assert "SOLO-ADMIN" not in log["cuerpo"]


@pytest.mark.parametrize("decision", ["OBSERVADO", "RECHAZADO"])
async def test_revision_exige_motivo_publico_y_repite_resultado(api_pagos, decision):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    id = (await reportar(client, usuario, operacion="42")).json()["comprobante_id"]
    r = respuesta(
        await revisar(client, junta, id, decision, motivo=None, notas="INTERNO"), 422, "Error"
    )
    assert "INTERNO" not in json.dumps(r)
    original = respuesta(await revisar(client, junta, id, decision), 200, "ResultadoRevision")
    # Cambios financieros posteriores no cambian la respuesta confirmada.
    await reportar(client, usuario, monto="5.00", operacion="43")
    assert (
        respuesta(await revisar(client, junta, id, decision), 200, "ResultadoRevision") == original
    )
    respuesta(await revisar(client, junta, id, decision, motivo="Otro motivo"), 409, "Error")
    respuesta(await revisar(client, junta, id, decision, notas="Otro comentario"), 409, "Error")
    duplicado = respuesta(await reportar(client, usuario, operacion="42"), 409, "Error")
    assert duplicado["error_code"] == (
        "VOUCHER_REQUIERE_SUBSANACION" if decision == "OBSERVADO" else "VOUCHER_RECHAZADO"
    )
    if decision == "RECHAZADO":
        respuesta(await subsanar(client, usuario, id), 409, "Error")


@pytest.mark.parametrize(
    "monto", ["1e26", "NaN", "Infinity", "0.00", "-1.00", "1.234", "10000000000.00"]
)
async def test_importes_invalidos_no_crean_archivos(api_pagos, monto):
    client, base = api_pagos
    respuesta(await reportar(client, await login(client), monto=monto), 422, "Error")
    async with base.sessions() as db:
        assert await db.scalar(select(ComprobantePago.id)) is None
    assert not VoucherStorage().directorio.exists()


async def test_subsanaciones_concurrentes_tienen_un_solo_ganador(api_pagos):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    id = (await reportar(client, usuario)).json()["comprobante_id"]
    await revisar(client, junta, id)
    results = await asyncio.gather(subsanar(client, usuario, id), subsanar(client, usuario, id))
    assert sorted(r.status_code for r in results) == [202, 409]
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ArchivoVoucher)) == 2
        assert await db.scalar(select(func.count()).select_from(EventoPagoOutbox)) == 3


@pytest.mark.parametrize("subsanacion", [False, True])
async def test_fallo_sql_revierte_archivo_auditoria_y_outbox(api_pagos, monkeypatch, subsanacion):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    if subsanacion:
        id = (await reportar(client, usuario)).json()["comprobante_id"]
        await revisar(client, junta, id)

    async def fallar(*args, **kwargs):
        raise RuntimeError("fallo controlado")

    monkeypatch.setattr(SQLAlchemyPagosRepository, "auditar", fallar)
    with pytest.raises(RuntimeError, match="controlado"):
        await (subsanar(client, usuario, id) if subsanacion else reportar(client, usuario))
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ArchivoVoucher)) == int(subsanacion)
        assert await db.scalar(select(func.count()).select_from(EventoPagoOutbox)) == (
            2 if subsanacion else 0
        )
        if subsanacion:
            assert (await db.get(ComprobantePago, UUID(id))).estado == "OBSERVADO"
    assert len(list(VoucherStorage().directorio.iterdir())) == int(subsanacion)


async def test_eventos_historicos_siguen_consumibles_sin_reescribirlos(api_pagos):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    id = (await reportar(client, usuario)).json()["comprobante_id"]
    await revisar(client, junta, id)
    async with base.sessions() as db, db.begin():
        for tipo in (
            "PagoReportadoEvent",
            "PagoObservadoEvent",
            "PagoRechazadoEvent",
            "PagoConciliadoEvent",
        ):
            eid = uuid4()
            payload = {
                "event_id": str(eid),
                "event_type": tipo,
                "version": 1,
                "producer": "service.pagos",
                "occurred_at": "2026-10-20T18:00:00Z",
                "data": {
                    "comprobante_id": id,
                    "departamento_id": str(
                        (await db.get(ComprobantePago, UUID(id))).departamento_id
                    ),
                    "condominio_id": base.cid,
                    "monto": "170.00",
                    "estado": "OBSERVADO",
                    "motivo": "Histórico",
                    "resultado": {"monto_imputado": "10.00", "nuevo_saldo_departamento": "160.00"},
                },
            }
            db.add(EventoPagoOutbox(id=eid, comprobante_id=UUID(id), payload=payload))
    async with base.sessions() as db:
        eventos = list(
            await db.scalars(
                select(EventoPagoOutbox).where(EventoPagoOutbox.payload.has_key("version"))
            )
        )
    for e in eventos:
        assert await consumir(base.sessions, e.payload) == 1
        assert await consumir(base.sessions, e.payload) == 0
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notificacion)) == 4
        for e in eventos:
            assert (await db.get(EventoPagoOutbox, e.id)).payload == e.payload


async def test_solicitudes_publicas_no_admiten_claves_privadas_ni_campos_extra(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    r = await client.post(
        "/api/v1/pagos/reportar", headers=usuario, json={"url_voucher": "NO-DIVULGAR"}
    )
    respuesta(r, 422, "Error")
    assert "NO-DIVULGAR" not in r.text
    respuesta(await client.post("/api/v1/pagos/vouchers", headers=usuario), 404, "Error")
    id = (await reportar(client, usuario)).json()["comprobante_id"]
    junta = await login(client, "admin", "Admin123!")
    await revisar(client, junta, id)
    respuesta(await subsanar(client, usuario, id, banco="BCP"), 422, "Error")
    ajeno = await login(client, "residente102", "Residente123!")
    respuesta(await subsanar(client, ajeno, id), 403, "Error")


async def test_reservas_y_comunicados_cumplen_los_esquemas_publicados(api_pagos):
    from src.tests.integration.test_pagos_db import solicitud

    client, base = api_pagos
    residente = await login(client, "residente102", "Residente123!")
    creada = respuesta(
        await client.post("/api/v1/reservas", headers=residente, json=solicitud(base, "102")),
        201,
        "ReservaConfirmada",
    )
    for r in (await client.get("/api/v1/reservas", headers=residente)).json():
        validar("Reserva", r)
    horarios = await client.get(
        f"/api/v1/areas/{creada['area_id']}/disponibilidad",
        headers=residente,
        params={"fecha": creada["fecha_reserva"]},
    )
    for h in horarios.json():
        validar("HorarioOcupado", h)
    respuesta(
        await client.post(f"/api/v1/reservas/{creada['id']}/cancelar", headers=residente),
        200,
        "ReservaCancelada",
    )
    junta = await login(client, "admin", "Admin123!")
    manual = {
        "condominio_id": base.cid,
        "departamento_id": creada["departamento_id"],
        "tipo_evento": "NOTIF_COMUNICADO_GENERAL",
        "canal": "EMAIL",
        "destinatario": "residente102@villabonita3.pe",
        "contexto": {
            "titulo": "Aviso manual",
            "mensaje": "Texto del aviso",
            "remitente": "Junta Directiva",
        },
    }
    validar("DespacharNotificacion", manual)
    log = respuesta(
        await client.post("/api/v1/notificaciones/despachar", headers=junta, json=manual),
        202,
        "Notificacion",
    )
    assert log["estado"] == "EN_COLA" and log["intentos"] == 0
    assert (
        respuesta(
            await client.post(f"/api/v1/notificaciones/reenviar/{log['id']}", headers=junta),
            200,
            "Notificacion",
        )
        == log
    )
    respuesta(
        await client.post(
            "/api/v1/notificaciones/comunicado-masivo",
            headers=junta,
            json={
                "condominio_id": base.cid,
                "titulo": "Aviso de contrato",
                "mensaje": "Mensaje de prueba de contrato",
            },
        ),
        202,
        "ComunicadoAceptado",
    )
    for n in (await client.get("/api/v1/notificaciones/logs", headers=junta)).json():
        validar("Notificacion", n)


@pytest.mark.parametrize(
    "contenido,status,codigo",
    [
        (b"GIF89a-otro-formato", 415, "FORMATO_VOUCHER_NO_SOPORTADO"),
        (b"\x89PNG\r\ntruncado", 422, "VOUCHER_INVALIDO"),
        (b"", 422, "VOUCHER_INVALIDO"),
        (b"x" * (5242880 + 1), 413, "ARCHIVO_DEMASIADO_GRANDE"),
    ],
    ids=["formato", "corrupto", "vacio", "limite"],
)
async def test_errores_de_archivo_reportar_y_subsanar(api_pagos, contenido, status, codigo):
    client, base = api_pagos
    usuario, junta = await login(client), await login(client, "admin", "Admin123!")
    assert (
        respuesta(await reportar(client, usuario, contenido), status, "Error")["error_code"]
        == codigo
    )
    id = (await reportar(client, usuario)).json()["comprobante_id"]
    await revisar(client, junta, id)
    assert (
        respuesta(await subsanar(client, usuario, id, contenido), status, "Error")["error_code"]
        == codigo
    )
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ArchivoVoucher)) == 1
        assert (await db.get(ComprobantePago, UUID(id))).estado == "OBSERVADO"


async def test_limite_exacto_y_tipo_real_no_dependen_del_nombre(api_pagos):
    from src.tests.pagos_db import did

    client, base = api_pagos
    usuario = await login(client)
    png = imagen()
    data = {
        "departamento_id": str(did()),
        "banco": " b c p ",
        "numero_operacion": " 000 1 ",
        "fecha_operacion": "2026-10-15",
        "monto": "0.01",
    }
    validar("ReportarPago", {**data, "archivo_voucher": "binary"})
    recibido = respuesta(
        await client.post(
            "/api/v1/pagos/reportar",
            headers=usuario,
            data=data,
            files={
                "archivo_voucher": (
                    "mentira.exe",
                    png + b"\0" * (5242880 - len(png)),
                    "application/octet-stream",
                )
            },
        ),
        202,
        "ComprobanteRecibido",
    )
    async with base.sessions() as db:
        c = await db.get(ComprobantePago, UUID(recibido["comprobante_id"]))
        assert c.banco_origen == "BCP" and c.numero_operacion == "1"
        archivo = await db.get(ArchivoVoucher, c.url_voucher)
        assert archivo.content_type == "image/png" and archivo.size_bytes == 5242880


async def test_openapi_registra_todas_las_operaciones_con72():
    formal = yaml.safe_load((CONTRATOS / "openapi/sprint-2.paths.yaml").read_text())
    runtime = app.openapi()["paths"]
    for ruta, operaciones in formal["paths"].items():
        for metodo in operaciones.keys() & {"get", "post", "put", "delete", "patch"}:
            assert metodo in runtime["/api/v1" + ruta], (ruta, metodo)
            assert (
                operaciones[metodo]["responses"].keys()
                <= runtime["/api/v1" + ruta][metodo]["responses"].keys()
            ), (ruta, metodo)
    assert "/api/v1/pagos/vouchers" not in runtime
    assert set(runtime["/api/v1/pagos/reportar"]["post"]["requestBody"]["content"]) == {
        "multipart/form-data"
    }


async def test_commit_confirmado_con_respuesta_perdida_no_borra_evidencia(api_pagos):
    from datetime import UTC, datetime, timedelta
    from io import BytesIO

    from fastapi import UploadFile
    from sqlalchemy import event

    from src.core.security import decode_access_token
    from src.modules.pagos.persistencia import PagosPersistentesService
    from src.modules.pagos.schemas import ReportarPagoRequest
    from src.tests.pagos_db import did

    client, base = api_pagos
    usuario = await login(client)
    actor = decode_access_token(usuario["Authorization"].split()[1])
    request = ReportarPagoRequest(
        departamento_id=did(),
        banco="BCP",
        numero_operacion="commit-incierto",
        fecha_operacion="2026-10-15",
        monto="170.00",
    )
    async with base.sessions() as db:

        @event.listens_for(db.sync_session, "after_commit", once=True)
        def perder_respuesta(session):
            raise RuntimeError("commit confirmado con respuesta perdida")

        with pytest.raises(RuntimeError, match="respuesta perdida"):
            await PagosPersistentesService(db).reportar(
                request, UploadFile(file=BytesIO(imagen())), actor
            )
    async with base.sessions() as db:
        pago = await db.scalar(select(ComprobantePago))
        assert VoucherStorage().ruta(pago.url_voucher).read_bytes() == imagen()
    await limpiar_pendientes(base.sessions, ahora=datetime.now(UTC) + timedelta(days=2))
    assert VoucherStorage().ruta(pago.url_voucher).exists()
    reintento = respuesta(
        await reportar(client, usuario, operacion="commit-incierto"), 200, "ComprobanteRecibido"
    )
    assert reintento["comprobante_id"] == str(pago.id)


async def test_error_inesperado_respeta_envelope_sin_divulgar_causa(api_pagos, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    client, _ = api_pagos
    usuario = await login(client)

    async def fallar(*args, **kwargs):
        raise RuntimeError("NO-DIVULGAR-CAUSA-INTERNA")

    monkeypatch.setattr(SQLAlchemyPagosRepository, "auditar", fallar)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as externo:
        response = await reportar(externo, usuario)
    assert respuesta(response, 500, "Error")["error_code"] == "ERROR_INTERNO"
    assert "NO-DIVULGAR" not in response.text
