"""Reparación legacy ensayada exclusivamente en esquemas PostgreSQL de pruebas."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from scripts.reconciliar_esquema_legacy import HEAD, reconciliar, validar_modelos

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def preparar_legacy(conn):
    # Solo el esquema efímero creado por db_usuarios; nunca se usa contra el despliegue.
    for table in (
        "notificaciones_alertas",
        "notificaciones_intentos",
        "notificaciones_logs",
        "notificaciones_eventos",
        "notificaciones_incidencias",
        "bloqueos_area",
    ):
        await conn.execute(text(f"DROP TABLE {table}"))
    await conn.execute(
        text("""CREATE TABLE notificaciones_logs (
        id UUID PRIMARY KEY, payload_resumen JSONB NOT NULL DEFAULT '{}')""")
    )
    await conn.execute(text("ALTER TABLE notificaciones_logs ENABLE ROW LEVEL SECURITY"))
    await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
    await conn.execute(text("INSERT INTO alembic_version VALUES ('20261021_0012')"))
    for columna in (
        "condominio_id",
        "moneda",
        "area_nombre",
        "fecha_cancelacion",
        "cancelado_por",
        "motivo_cancelacion",
    ):
        await conn.execute(text(f"ALTER TABLE reservas DROP COLUMN {columna}"))
    await conn.execute(
        text(
            "ALTER TABLE reservas ALTER COLUMN usuario_id SET NOT NULL, ALTER COLUMN zona_horaria TYPE VARCHAR(30)"
        )
    )
    await conn.execute(text("DROP INDEX idx_reservas_area_fecha"))
    await conn.execute(
        text("CREATE INDEX idx_reservas_area_fecha ON reservas (area_id, fecha_reserva)")
    )
    await conn.execute(text("DROP INDEX ix_eventos_reserva_outbox_reserva_id"))
    await conn.execute(
        text("ALTER TABLE revisiones_pago DROP COLUMN archivo_nombre, DROP COLUMN notas_internas")
    )
    await conn.execute(
        text(
            "ALTER TABLE archivos_voucher ADD CONSTRAINT legacy_archivo_comprobante UNIQUE (comprobante_id)"
        )
    )
    rid = uuid4()
    await conn.execute(
        text("""INSERT INTO reservas
        (id,area_id,departamento_id,usuario_id,fecha_reserva,hora_inicio,hora_fin,costo_reserva,estado,creado_en,zona_horaria)
        SELECT :rid,a.id,d.id,u.id,'2026-10-30','14:00','16:00',35.75,'CANCELADA','2026-10-20T15:00:00Z','UTC'
        FROM areas_comunes a JOIN edificios e ON e.condominio_id=a.condominio_id
        JOIN departamentos d ON d.edificio_id=e.id CROSS JOIN usuarios u LIMIT 1"""),
        {"rid": rid},
    )
    await conn.execute(
        text("""INSERT INTO cancelaciones_reserva
        SELECT id,usuario_id,'Motivo histórico','2026-10-21T15:00:00Z',jsonb_build_object('historico',true)
        FROM reservas WHERE id=:rid"""),
        {"rid": rid},
    )
    await conn.execute(
        text("""INSERT INTO eventos_reserva_outbox (id,reserva_id,payload,creado_en)
        VALUES (:eid,:rid,jsonb_build_object('version',1,'historico',true),'2026-10-21T15:00:00Z')"""),
        {"eid": uuid4(), "rid": rid},
    )
    return rid


@pytest.mark.parametrize(
    "fallo", [None, "revision", "notificaciones", "cancelacion", "cobro", "validacion_final"]
)
async def test_reconcilia_o_revierte_atomicamente(db_usuarios, monkeypatch, fallo):
    # Ensayo del reparador fijado a su revisión original, no autorización para head nuevo.
    monkeypatch.setattr(
        "scripts.reconciliar_esquema_legacy.ScriptDirectory.from_config",
        lambda _: SimpleNamespace(get_current_head=lambda: HEAD),
    )
    async with db_usuarios.engine.connect() as conn:
        transaction = await conn.begin()
        try:
            rid = await preparar_legacy(conn)
            if fallo == "revision":
                await conn.execute(text("UPDATE alembic_version SET version_num='otra_revision'"))
            elif fallo == "notificaciones":
                await conn.execute(
                    text("INSERT INTO notificaciones_logs (id) VALUES (:id)"), {"id": uuid4()}
                )
            elif fallo == "cancelacion":
                await conn.execute(
                    text("DELETE FROM cancelaciones_reserva WHERE reserva_id=:id"), {"id": rid}
                )
            elif fallo == "cobro":
                await conn.execute(
                    text("""ALTER TABLE cobros_reserva
                    ALTER COLUMN comprobante_id DROP NOT NULL, ALTER COLUMN monto DROP NOT NULL""")
                )
                await conn.execute(
                    text("INSERT INTO cobros_reserva (reserva_id) VALUES (:id)"), {"id": rid}
                )
            elif fallo == "validacion_final":

                def rechazar(_conn):
                    raise RuntimeError("Fallo al final del DDL")

                monkeypatch.setattr("scripts.reconciliar_esquema_legacy.validar_modelos", rechazar)
            if fallo:
                with pytest.raises(RuntimeError):
                    async with conn.begin_nested():
                        await conn.run_sync(reconciliar)
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    != "20261021_0015"
                )
                assert await conn.scalar(text("SELECT to_regclass('bloqueos_area')")) is None
                assert await conn.scalar(text("SELECT count(*) FROM reservas")) == 1
                return
            result = await conn.run_sync(reconciliar)
            assert result["revision"] == "20261021_0015"
            await conn.run_sync(validar_modelos)
            row = (
                (await conn.execute(text("SELECT * FROM reservas WHERE id=:id"), {"id": rid}))
                .mappings()
                .one()
            )
            assert row["fecha_cancelacion"].isoformat() == "2026-10-21T15:00:00+00:00"
            assert row["motivo_cancelacion"] == "Motivo histórico"
            assert row["cancelado_por"] == row["usuario_id"]
            assert str(row["costo_reserva"]) == "35.75" and row["zona_horaria"] == "UTC"
            assert (
                await conn.scalar(text("SELECT payload->>'historico' FROM eventos_reserva_outbox"))
                == "true"
            )
            assert await conn.scalar(text("SELECT count(*) FROM cancelaciones_reserva")) == 1
            with pytest.raises(RuntimeError, match="marcador legacy"):
                async with conn.begin_nested():
                    await conn.run_sync(reconciliar)
        finally:
            await transaction.rollback()


async def test_reparador_legacy_rechaza_head_financiero_actual():
    with pytest.raises(RuntimeError, match="El head cambió"):
        reconciliar(None)
