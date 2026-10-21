"""Dos recorridos críticos CON-46 con PostgreSQL y sesiones independientes."""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.exc import SQLAlchemyError

from src.core.models_audit import AuditoriaLogORM
from src.modules.pagos.models import ComprobantePago
from src.modules.reservas import router
from src.modules.reservas.cancelaciones import CancelacionesService
from src.modules.reservas.models import (
    CancelacionReserva,
    CobroReserva,
    EventoReservaOutbox,
    Reserva,
)
from src.modules.reservas.worker import publicar_pendientes
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_catalogo_areas_db import turno

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
AREA = "11111111-1111-1111-1111-111111111101"


def migrar(connection):
    revision = import_module("migrations.versions.20261021_0012_cancelaciones_reserva")
    with Operations.context(MigrationContext.configure(connection)):
        revision.upgrade()
        revision.downgrade()
        # Reproduce el esquema observado en Supabase: creador obligatorio,
        # campo histórico opcional y ausencia de zona_horaria.
        op.create_table(
            "reservas",
            sa.Column(
                "id", PG_UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
            ),
            sa.Column(
                "area_id",
                PG_UUID(),
                sa.ForeignKey("areas_comunes.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "departamento_id",
                PG_UUID(),
                sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "usuario_id",
                PG_UUID(),
                sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("fecha_reserva", sa.Date(), nullable=False),
            sa.Column("hora_inicio", sa.Time(), nullable=False),
            sa.Column("hora_fin", sa.Time(), nullable=False),
            sa.Column("costo_reserva", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("estado", sa.String(20), nullable=False, server_default="SOLICITADA"),
            sa.Column("motivo_rechazo", sa.Text()),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            comment="Baseline histórico de Supabase para CON-46",
        )
        op.execute("ALTER TABLE reservas ENABLE ROW LEVEL SECURITY")
        revision.upgrade()
        columnas = {c["name"]: c for c in sa.inspect(connection).get_columns("reservas")}
        assert not columnas["usuario_id"]["nullable"]
        assert "motivo_rechazo" in columnas and "zona_horaria" in columnas
        assert (
            sa.inspect(connection).get_table_comment("reservas")["text"]
            == "Baseline histórico de Supabase para CON-46"
        )


@pytest_asyncio.fixture
async def caso_cancelacion(api_pagos):
    client, base = api_pagos
    async with base.engine.begin() as conn:
        await conn.run_sync(migrar)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    creada = await client.post("/api/v1/reservas", headers=residente, json=turno(base, AREA))
    assert creada.status_code == 201, creada.text
    return client, base, residente, UUID(creada.json()["id"])


def validar_evento(payload):
    carpeta = Path(__file__).resolve().parents[3] / "specs/03-contracts/events/schemas"
    base = "https://schemas.condomanager.test/"
    contrato = json.loads((carpeta / "reserva-cancelada.v1.schema.json").read_text())
    contrato["$id"] = base + "reserva-cancelada.v1.schema.json"
    envelope = json.loads((carpeta / "event-envelope.v1.schema.json").read_text())
    registry = Registry().with_resource(
        base + "event-envelope.v1.schema.json", Resource.from_contents(envelope)
    )
    Draft202012Validator(contrato, registry=registry, format_checker=FormatChecker()).validate(
        payload
    )


async def test_cancelacion_concurrente_persistencia_ajuste_y_evento_unicos(
    caso_cancelacion, monkeypatch
):
    client, base, residente, rid = caso_cancelacion
    # Precondición del consumidor: reserva SQL y cobro efectivo ya registrado
    # por el flujo financiero. La tarifa por sí sola nunca acredita este cobro.
    datos = router.RESERVAS_REGISTRADAS[rid]
    creador_id = UUID(datos["usuario_id"])
    comprobante_id = uuid4()
    async with base.sessions() as db, db.begin():
        registro = {c.name: datos[c.name] for c in Reserva.__table__.columns}
        registro["usuario_id"] = creador_id
        db.add(Reserva(**registro))
        db.add(
            ComprobantePago(
                id=comprobante_id,
                departamento_id=datos["departamento_id"],
                banco_origen="BCP",
                numero_operacion=uuid4().hex,
                fecha_operacion=datetime.now(UTC).date(),
                monto=Decimal("50.00"),
                url_voucher="evidencia-registrada",
                idempotency_hash=uuid4().hex * 2,
                estado="APROBADO",
                conciliado_en=datetime.now(UTC),
            )
        )
        await db.flush()
        db.add(
            CobroReserva(
                reserva_id=rid,
                comprobante_id=comprobante_id,
                monto=Decimal("50.00"),
                monto_compensado=Decimal("10.00"),
                reembolsable=True,
            )
        )
    ruta = f"/api/v1/reservas/{rid}/cancelar"
    for cuenta, password in (
        ("inquilino504@villabonita3.pe", "Inquilino123!"),
        ("auditor@villabonita3.pe", "Auditor123!"),
    ):
        ajeno = await login(client, cuenta, password)
        assert (await client.post(ruta, headers=ajeno, json={"es_admin": True})).status_code == 403
    respuestas = await asyncio.wait_for(
        asyncio.gather(
            client.post(ruta, headers=residente, json={"motivo": "Cambio de planes"}),
            client.post(ruta, headers=residente, json={"motivo": "Reintento concurrente"}),
        ),
        timeout=15,
    )
    assert [r.status_code for r in respuestas] == [200, 200], [r.text for r in respuestas]
    original = respuestas[0].json()
    assert respuestas[1].json() == original
    assert original["ajuste_economico"] == {
        "estado": "PENDIENTE",
        "monto": "40.00",
        "referencia": None,
    }
    # Otra instancia no puede ocultar SQL con una copia piloto desactualizada.
    monkeypatch.setattr(router, "RESERVAS_REGISTRADAS", {rid: {**datos, "estado": "CONFIRMADA"}})
    calendario = await client.get(
        f"/api/v1/areas/{AREA}/disponibilidad",
        headers=residente,
        params={"fecha": datos["fecha_reserva"].isoformat()},
    )
    assert calendario.status_code == 200 and calendario.json() == []
    nueva = await client.post("/api/v1/reservas", headers=residente, json=turno(base, AREA))
    assert nueva.status_code == 201, nueva.text
    assert nueva.json()["id"] != str(rid)
    monkeypatch.setattr(router, "RESERVAS_REGISTRADAS", {})
    assert (await client.post(ruta, headers=residente)).json() == original
    historial = await client.get("/api/v1/reservas", headers=residente)
    assert historial.status_code == 200 and historial.json()[0]["estado"] == "CANCELADA"
    async with base.sessions() as db:
        assert (await db.get(Reserva, rid)).estado == "CANCELADA"
        assert (await db.get(Reserva, rid)).usuario_id == UUID(datos["usuario_id"])
        assert await db.scalar(select(func.count()).select_from(CancelacionReserva)) == 1
        assert await db.scalar(select(func.count()).select_from(EventoReservaOutbox)) == 1
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).where(
                    AuditoriaLogORM.accion_ejecutada == "RESERVA_CANCELADA"
                )
            )
        )
        assert len(logs) == 1 and logs[0].actor_tipo == "RESIDENTE"
        evento = await db.scalar(select(EventoReservaOutbox))
        assert evento.publicado_en is None
        validar_evento(evento.payload)

    class Transporte:
        def __init__(self):
            self.eventos = []

        async def xadd(self, stream, data):
            self.eventos.append(json.loads(data["event"]))

    transporte = Transporte()
    await publicar_pendientes(transporte, base.sessions)
    await publicar_pendientes(transporte, base.sessions)
    assert len(transporte.eventos) == 1
    async with base.sessions() as db:
        assert (await db.scalar(select(EventoReservaOutbox))).publicado_en is not None


async def test_fallo_transaccional_revierte_adopcion_auditoria_y_evento(
    caso_cancelacion, monkeypatch
):
    client, base, residente, rid = caso_cancelacion
    original = CancelacionesService._guardar

    async def fallar(self, *args):
        await original(self, *args)
        # Fallo después del flush: comprueba rollback real de todos los registros.
        raise SQLAlchemyError("Fallo de persistencia inyectado por la prueba")

    monkeypatch.setattr(CancelacionesService, "_guardar", fallar)
    ruta = f"/api/v1/reservas/{rid}/cancelar"
    response = await client.post(ruta, headers=residente)
    assert (
        response.status_code == 503 and response.json()["error_code"] == "CANCELACION_NO_DISPONIBLE"
    )
    assert router.RESERVAS_REGISTRADAS[rid]["estado"] == "CONFIRMADA"
    async with base.sessions() as db:
        assert await db.get(Reserva, rid) is None
        assert await db.scalar(select(func.count()).select_from(CancelacionReserva)) == 0
        assert await db.scalar(select(func.count()).select_from(EventoReservaOutbox)) == 0
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada == "RESERVA_CANCELADA")
            )
            == 0
        )
    monkeypatch.setattr(CancelacionesService, "_guardar", original)
    reintento = await client.post(ruta, headers=residente)
    assert reintento.status_code == 200, reintento.text
    assert reintento.json()["ajuste_economico"]["estado"] == "NO_APLICA"
    async with base.sessions() as db:
        assert (await db.get(Reserva, rid)).usuario_id == UUID(
            router.RESERVAS_REGISTRADAS[rid]["usuario_id"]
        )
