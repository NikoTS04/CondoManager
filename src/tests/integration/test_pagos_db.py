"""Aceptación real CON-22/70/42: login SQL, archivos y sesiones independientes."""

import asyncio
import io
import json
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image
from sqlalchemy import func, select, text

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_persistencia import ArchivoVoucher, EventoPagoOutbox, RevisionPago
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.storage import VoucherStorage
from src.modules.pagos.worker import limpiar_pendientes, publicar_pendientes
from src.modules.reservas.models import Reserva
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioDepartamento
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


def imagen():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


async def login(client, cuenta="moroso402", password="Moroso123!"):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": cuenta + "@villabonita3.pe",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


async def subir(client, headers, numero="402", contenido=None):
    response = await client.post(
        "/api/v1/pagos/vouchers",
        headers=headers,
        data={"departamento_id": str(did(numero))},
        files={
            "voucher_file": (
                "../../original.png",
                contenido if contenido is not None else imagen(),
                "image/png",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["url_voucher"]


async def reportar(client, headers, nombre, *, numero="402", monto="170.00", operacion=None):
    return await client.post(
        "/api/v1/pagos/reportar",
        headers=headers,
        json={
            "departamento_id": str(did(numero)),
            "banco": "BCP",
            "numero_operacion": operacion or uuid4().hex,
            "fecha_operacion": "2026-10-15",
            "monto": monto,
            "url_voucher": nombre,
        },
    )


def solicitud(base, numero="402"):
    return {
        "condominio_id": base.cid,
        "departamento_id": str(did(numero)),
        "area_id": "11111111-1111-1111-1111-111111111101",
        "fecha_reserva": (date.today() + timedelta(days=10)).isoformat(),
        "hora_inicio": "19:00",
        "hora_fin": "22:00",
    }


async def test_recorrido_persistente_reporte_revision_y_solvencia(api_pagos):
    client, base = api_pagos
    residente = await login(client)
    junta = await login(client, "admin", "Admin123!")
    before = await client.get(f"/api/v1/pagos/solvencia/{did()}", headers=residente)
    assert before.json()["saldo_vencido"] == "170.00"
    unidades = await client.get("/api/v1/cuotas/departamentos", headers=residente)
    assert unidades.status_code == 200
    assert len(unidades.json()) == 1 and unidades.json()[0]["estado_financiero"] == "EN_MORA"
    rechazo = await client.post("/api/v1/reservas", headers=residente, json=solicitud(base))
    assert (
        rechazo.status_code == 403 and rechazo.json()["detail"]["error_code"] == "DEUDA_MORA_ACTIVA"
    )
    async with base.sessions() as db:
        assert await db.scalar(select(Reserva.id)) is None
    nombre = await subir(client, residente)
    creado = await reportar(client, residente, nombre)
    assert creado.status_code == 202, creado.text
    id = creado.json()["comprobante_id"]
    async with base.sessions() as db:
        comprobante = await db.get(ComprobantePago, UUID(id))
        assert comprobante.url_voucher == nombre and "/" not in nombre
        cuota = await db.scalar(
            select(CuotaMantenimiento).where(CuotaMantenimiento.departamento_id == did())
        )
        assert cuota.monto_pagado == Decimal("0.00")
        assert await db.scalar(select(func.count()).select_from(ImputacionPago)) == 0
    assert (
        await client.post("/api/v1/reservas", headers=residente, json=solicitud(base))
    ).status_code == 403
    descarga = await client.get(f"/api/v1/pagos/{id}/voucher", headers=residente)
    assert descarga.status_code == 200 and descarga.content == imagen()
    assert descarga.headers["cache-control"] == "no-store"
    revision = await client.post(
        f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
    )
    assert revision.status_code == 200, revision.text
    assert revision.json()["monto_imputado"] == "170.00"
    assert revision.json()["departamento_habilitado_reservas"] is True
    assert (
        await client.get(f"/api/v1/pagos/{id}/resultado", headers=residente)
    ).json() == revision.json()
    assert (await client.get(f"/api/v1/pagos/solvencia/{did()}", headers=residente)).json()[
        "saldo_vencido"
    ] == "0.00"
    unidades = await client.get("/api/v1/cuotas/departamentos", headers=residente)
    assert unidades.json()[0]["estado_financiero"] == "AL_DIA"
    assert (
        await client.post("/api/v1/reservas", headers=residente, json=solicitud(base))
    ).status_code == 201
    listado = await client.get("/api/v1/pagos/comprobantes", headers=residente)
    assert listado.json()[0]["estado"] == "CONCILIADO"
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ImputacionPago)) == 1
        eventos = list(await db.scalars(select(EventoPagoOutbox)))
        assert len(eventos) == 2 and all(e.publicado_en is None for e in eventos)
        assert {e.payload["event_type"] for e in eventos} == {
            "PagoReportadoEvent",
            "PagoConciliadoEvent",
        }
        schemas = Path(__file__).resolve().parents[3] / "specs/03-contracts/events/schemas"
        contrato = json.loads((schemas / "pago-sprint-2.schema.json").read_text())
        historico = json.loads((schemas / "pago-conciliado.schema.json").read_text())
        for evento in eventos:
            Draft202012Validator(contrato, format_checker=FormatChecker()).validate(evento.payload)
            if evento.payload["event_type"] == "PagoConciliadoEvent":
                Draft202012Validator(historico, format_checker=FormatChecker()).validate(
                    evento.payload
                )
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        for anterior, posterior in zip(logs, logs[1:]):
            assert posterior.hash_previo == anterior.hash_actual
        assert all(log.hash_actual and log.motivo and log.estado_posterior for log in logs)


async def test_reintentos_concurrentes_y_datos_equivalentes(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    nombre = await subir(client, usuario)
    respuestas = await asyncio.gather(
        reportar(client, usuario, nombre, operacion="00012345"),
        reportar(client, usuario, nombre, operacion=" 12345 "),
    )
    assert sorted(r.status_code for r in respuestas) == [200, 202]
    assert len({r.json()["comprobante_id"] for r in respuestas}) == 1
    repetido = await reportar(client, usuario, nombre, operacion="00012345")
    assert repetido.status_code == 200 and repetido.json()["error_code"] == "VOUCHER_EN_EVALUACION"
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ComprobantePago)) == 1
        assert await db.scalar(select(func.count()).select_from(EventoPagoOutbox)) == 1


async def test_aprobaciones_concurrentes_no_duplican_fondos(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    junta = await login(client, "admin", "Admin123!")
    nuevo = await reportar(client, usuario, await subir(client, usuario), monto="200.00")
    id = nuevo.json()["comprobante_id"]
    respuestas = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
            )
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    async with base.sessions() as db:
        assert (await db.get(Departamento, did())).saldo_a_favor == Decimal("30.00")
        assert await db.scalar(select(func.count()).select_from(RevisionPago)) == 1
        assert await db.scalar(select(func.sum(ImputacionPago.monto_aplicado))) == Decimal("170.00")


@pytest.mark.parametrize("decision", ["OBSERVADO", "RECHAZADO"])
async def test_revision_sin_aplicar_y_motivo_obligatorio(api_pagos, decision):
    client, base = api_pagos
    usuario = await login(client)
    junta = await login(client, "admin", "Admin123!")
    nuevo = await reportar(client, usuario, await subir(client, usuario))
    id = nuevo.json()["comprobante_id"]
    ruta = f"/api/v1/pagos/{id}/conciliar"
    assert (await client.post(ruta, headers=junta, json={"decision": decision})).status_code == 422
    response = await client.post(
        ruta,
        headers=junta,
        json={"decision": decision, "motivo_rechazo": "Falta verificar operación"},
    )
    assert response.status_code == 200 and response.json()["monto_imputado"] == "0.00"
    assert response.json()["estado_final"] == decision
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ImputacionPago)) == 0
        assert (await db.get(ComprobantePago, UUID(id))).estado == decision
    if decision == "OBSERVADO":
        assert (
            await client.post(ruta, headers=junta, json={"decision": "APROBADO"})
        ).status_code == 200


async def test_rollback_financiero_auditoria_y_evento(api_pagos, monkeypatch):
    client, base = api_pagos
    usuario = await login(client)
    junta = await login(client, "admin", "Admin123!")
    nuevo = await reportar(client, usuario, await subir(client, usuario), monto="200.00")
    id = nuevo.json()["comprobante_id"]

    async def fallar(*args, **kwargs):
        raise RuntimeError("Fallo de auditoría controlado")

    monkeypatch.setattr(SQLAlchemyPagosRepository, "auditar", fallar)
    with pytest.raises(RuntimeError, match="auditoría"):
        await client.post(
            f"/api/v1/pagos/{id}/conciliar", headers=junta, json={"decision": "APROBADO"}
        )
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, UUID(id))).estado == "EN_REVISION"
        assert (await db.get(Departamento, did())).saldo_a_favor == Decimal("0.00")
        assert await db.scalar(select(func.count()).select_from(ImputacionPago)) == 0
        assert await db.scalar(select(func.count()).select_from(RevisionPago)) == 0
        assert await db.scalar(select(func.count()).select_from(EventoPagoOutbox)) == 1


async def test_voucher_privado_y_proteccion_de_subida(api_pagos):
    client, base = api_pagos
    propio = await login(client)
    ajeno = await login(client, "residente102", "Residente123!")
    auditor = await login(client, "auditor", "Auditor123!")
    nombre = await subir(client, propio)
    assert (await reportar(client, ajeno, nombre, numero="102")).status_code == 422
    nuevo = await reportar(client, propio, nombre, operacion="12345")
    id = nuevo.json()["comprobante_id"]
    assert (await client.get(f"/api/v1/pagos/{id}/voucher", headers=ajeno)).status_code == 403
    assert (await client.get(f"/api/v1/pagos/{id}/voucher", headers=auditor)).status_code == 200
    assert (await client.get(f"/api/v1/pagos/{id}/resultado", headers=ajeno)).status_code == 403
    assert (await client.get("/api/v1/pagos/comprobantes", headers=ajeno)).json() == []
    reutilizado = await reportar(client, ajeno, nombre, numero="102", operacion="12345")
    assert reutilizado.status_code == 409 and "comprobante_id" not in reutilizado.json()
    assert (await reportar(client, auditor, nombre)).status_code == 403
    assert (await reportar(client, propio, nombre, operacion="nueva-operacion")).status_code == 422
    for ref in ("../secreto.png", "https://externo/voucher.png", "blob:temporal"):
        assert (await reportar(client, propio, ref)).status_code == 422


@pytest.mark.parametrize(
    "contenido,codigo",
    [(b"no es png", 422), (b"x" * (5 * 1024 * 1024 + 1), 413)],
    ids=["contenido_invalido", "archivo_grande"],
)
async def test_subida_invalida_no_crea_registros(api_pagos, contenido, codigo):
    client, base = api_pagos
    usuario = await login(client)
    response = await client.post(
        "/api/v1/pagos/vouchers",
        headers=usuario,
        data={"departamento_id": str(did())},
        files={"voucher_file": ("imagen.png", contenido, "image/png")},
    )
    assert response.status_code == codigo
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ArchivoVoucher)) == 0
    assert not VoucherStorage().directorio.exists()


async def test_fallo_disco_no_informa_exito(api_pagos, monkeypatch):
    client, base = api_pagos
    usuario = await login(client)
    from pathlib import Path

    def fallar(*args, **kwargs):
        raise PermissionError("Permiso denegado de prueba")

    monkeypatch.setattr(Path, "mkdir", fallar)
    response = await client.post(
        "/api/v1/pagos/vouchers",
        headers=usuario,
        data={"departamento_id": str(did())},
        files={"voucher_file": ("imagen.png", imagen(), "image/png")},
    )
    assert response.status_code == 503
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ArchivoVoucher)) == 0


async def test_solvencia_por_unidad_y_revocacion_real(api_pagos):
    client, base = api_pagos
    async with base.sessions() as db, db.begin():
        db.add(
            UsuarioDepartamento(
                usuario_id=id_demo("moroso402@villabonita3.pe"),
                departamento_id=did("102"),
                tipo_relacion="COPROPIETARIO",
                es_activo=True,
            )
        )
    usuario = await login(client)
    for numero, esperada in (("402", False), ("102", True)):
        response = await client.get(f"/api/v1/pagos/solvencia/{did(numero)}", headers=usuario)
        assert response.status_code == 200 and response.json()["habilitado_reservas"] is esperada
    async with base.sessions() as db, db.begin():
        vinculo = await db.scalar(
            select(UsuarioDepartamento).where(
                UsuarioDepartamento.usuario_id == id_demo("moroso402@villabonita3.pe"),
                UsuarioDepartamento.departamento_id == did("102"),
            )
        )
        vinculo.es_activo = False
    assert (
        await client.get(f"/api/v1/pagos/solvencia/{did('102')}", headers=usuario)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/pagos/solvencia/{uuid4()}", headers=usuario)
    ).status_code == 403


async def test_relay_recupera_evento_con_identificador_estable(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    await reportar(client, usuario, await subir(client, usuario))

    class RedisConFallo:
        mensajes = []
        fallar = True

        async def xadd(self, stream, mensaje):
            self.mensajes.append((stream, mensaje))
            if self.fallar:
                raise ConnectionError("Redis aceptó pero se perdió la respuesta")

    redis = RedisConFallo()
    with pytest.raises(ConnectionError):
        await publicar_pendientes(redis, base.sessions)
    async with base.sessions() as db:
        assert (await db.scalar(select(EventoPagoOutbox))).publicado_en is None
    redis.fallar = False
    await publicar_pendientes(redis, base.sessions)
    await publicar_pendientes(redis, base.sessions)
    assert len(redis.mensajes) == 2 and redis.mensajes[0] == redis.mensajes[1]


async def test_limpieza_recuperable_no_borra_adjuntos(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    adjunto = await subir(client, usuario)
    await reportar(client, usuario, adjunto)
    pendiente = await subir(client, usuario)
    limite = datetime.now(UTC) - timedelta(days=2)
    async with base.sessions() as db, db.begin():
        for nombre in (adjunto, pendiente):
            (await db.get(ArchivoVoucher, nombre)).creado_en = limite
    storage = VoucherStorage()
    huerfano, _ = storage.guardar(imagen())
    for nombre in (adjunto, pendiente, huerfano):
        os.utime(storage.ruta(nombre), (limite.timestamp(), limite.timestamp()))
    await limpiar_pendientes(base.sessions, storage)
    assert storage.ruta(adjunto).exists()
    assert not (storage.directorio / pendiente).exists()
    assert not (storage.directorio / huerfano).exists()
    async with base.sessions() as db:
        assert await db.get(ArchivoVoucher, pendiente) is None
        assert await db.get(ArchivoVoucher, adjunto) is not None


async def test_adopcion_de_tablas_conserva_registros(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    nuevo = await reportar(client, usuario, await subir(client, usuario))
    id = UUID(nuevo.json()["comprobante_id"])
    revision = import_module("migrations.versions.20261020_0009_pagos_persistentes")

    def readoptar(conn):
        conn.execute(text("COMMENT ON TABLE comprobantes_pago IS 'baseline externo'"))
        conn.execute(text("COMMENT ON TABLE imputaciones_pago IS 'baseline externo'"))
        with Operations.context(MigrationContext.configure(conn)):
            revision.downgrade()
            revision.upgrade()

    async with base.engine.begin() as conn:
        await conn.run_sync(readoptar)
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, id)).estado == "EN_REVISION"


async def test_nueva_conexion_recupera_reporte_y_archivo(api_pagos):
    client, base = api_pagos
    usuario = await login(client)
    nombre = await subir(client, usuario)
    nuevo = await reportar(client, usuario, nombre)
    await base.engine.dispose()  # Simula perder todas las conexiones y el estado del pool.
    id = nuevo.json()["comprobante_id"]
    assert (await client.get(f"/api/v1/pagos/{id}/voucher", headers=usuario)).content == imagen()
    async with base.sessions() as db:
        assert (await db.get(ComprobantePago, UUID(id))).url_voucher == nombre
