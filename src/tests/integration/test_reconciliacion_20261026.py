"""Ensayo del incidente 0013; solo esquemas efímeros PostgreSQL."""

from importlib import import_module
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from scripts import reconciliar_esquema_20261026 as reparacion
from scripts.reconciliar_esquema_legacy import huellas

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


def preparar(conn):
    with Operations.context(MigrationContext.configure(conn)):
        for nombre in reversed(reparacion.REVISIONES):
            import_module("migrations.versions." + nombre).downgrade()
    conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
    conn.execute(text("INSERT INTO alembic_version VALUES ('20261021_0013')"))
    conn.execute(text("ALTER TABLE eventos_reserva_outbox DROP CONSTRAINT uq_evento_reserva_tipo"))
    conn.execute(text("ALTER TABLE eventos_reserva_outbox ALTER COLUMN tipo DROP NOT NULL"))
    rid, eid = uuid4(), uuid4()
    conn.execute(text("""INSERT INTO reservas
        (id,area_id,departamento_id,usuario_id,condominio_id,moneda,area_nombre,
         fecha_reserva,hora_inicio,hora_fin,costo_reserva,estado,zona_horaria,creado_en,
         fecha_cancelacion,cancelado_por,motivo_cancelacion)
        SELECT :rid,a.id,d.id,u.id,a.condominio_id,'PEN',a.nombre,
         '2026-10-20','14:00','16:00',35.75,'CANCELADA','America/Lima',
         '2026-10-19T15:00:00Z','2026-10-20T15:00:00Z',u.id,'Motivo histórico'
        FROM areas_comunes a JOIN edificios e ON e.condominio_id=a.condominio_id
        JOIN departamentos d ON d.edificio_id=e.id CROSS JOIN usuarios u LIMIT 1"""), {"rid": rid})
    conn.execute(text("""INSERT INTO cancelaciones_reserva
        SELECT id,usuario_id,motivo_cancelacion,fecha_cancelacion,
        jsonb_build_object('historico',true) FROM reservas WHERE id=:rid"""), {"rid": rid})
    conn.execute(text("""INSERT INTO eventos_reserva_outbox
        (id,reserva_id,tipo,payload,creado_en,publicado_en)
        VALUES (:eid,:rid,'ReservaCanceladaEvent',
        jsonb_build_object('event_type','ReservaCanceladaEvent','historico',true),
        '2026-10-20T15:00:00Z','2026-10-20T15:00:01Z')"""), {"eid": eid, "rid": rid})
    return rid


def respaldo(conn):
    inspector = inspect(conn)
    tablas = {t: [c["name"] for c in inspector.get_columns(t)] for t in inspector.get_table_names()}
    firmas = huellas(conn, tablas)
    esquema = conn.scalar(text("SELECT current_schema()"))
    return {"tables": {esquema + "." + t: {"columns": columnas, "fingerprint": list(firmas[t])}
                       for t, columnas in tablas.items()}}


@pytest.mark.parametrize("fallo", [None, "revision", "respaldo", "evento", "duplicado", "contexto",
                                  "cobro", "esquema", "validacion_final"])
async def test_repara_o_revierte_sin_perder_historia(db_usuarios, monkeypatch, fallo):
    async with db_usuarios.engine.connect() as conn:
        transaction = await conn.begin()
        try:
            rid = await conn.run_sync(preparar)
            if fallo == "revision":
                await conn.execute(text("UPDATE alembic_version SET version_num='otra'"))
            elif fallo == "evento":
                await conn.execute(text("UPDATE eventos_reserva_outbox SET tipo=NULL"))
            elif fallo == "duplicado":
                await conn.execute(text("""INSERT INTO eventos_reserva_outbox
                    (id,reserva_id,tipo,payload,creado_en,publicado_en)
                    SELECT :id,reserva_id,tipo,payload,creado_en,publicado_en
                    FROM eventos_reserva_outbox"""), {"id": uuid4()})
            elif fallo == "contexto":
                await conn.execute(text("UPDATE reservas SET motivo_cancelacion='distinto'"))
            elif fallo == "cobro":
                await conn.execute(text("""INSERT INTO comprobantes_pago
                    (id,departamento_id,banco_origen,numero_operacion,fecha_operacion,monto,
                     url_voucher,idempotency_hash,estado,creado_en)
                    SELECT :id,departamento_id,'BCP','123','2026-10-20',35.75,
                    'historico.pdf','hash','APROBADO',now() FROM reservas LIMIT 1"""), {"id": uuid4()})
                await conn.execute(text("""INSERT INTO cobros_reserva
                    SELECT r.id,c.id,35.75,0,true FROM reservas r CROSS JOIN comprobantes_pago c LIMIT 1"""))
            elif fallo == "esquema":
                await conn.execute(text("ALTER TABLE cobros_reserva DROP CONSTRAINT ck_cobro_reserva_monto"))
            elif fallo == "validacion_final":
                original = reparacion.validar_modelos

                def validar(c, tablas=None):
                    if tablas is None:
                        raise RuntimeError("Fallo posterior al DDL")
                    original(c, tablas)

                monkeypatch.setattr(reparacion, "validar_modelos", validar)
            copia = await conn.run_sync(respaldo)
            if fallo == "respaldo":
                copia["tables"][db_usuarios.esquema + ".reservas"]["fingerprint"][0] += 1
            if fallo:
                with pytest.raises(RuntimeError):
                    async with conn.begin_nested():
                        await conn.run_sync(reparacion.reconciliar, copia)
                assert await conn.scalar(text("SELECT to_regclass('devengos_mora')")) is None
                assert await conn.scalar(text("SELECT count(*) FROM reservas")) == 1
                assert await conn.scalar(text("SELECT count(*) FROM cancelaciones_reserva")) == 1
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) != reparacion.HEAD
                assert await conn.run_sync(lambda c: "uq_evento_reserva_tipo" not in {
                    x["name"] for x in inspect(c).get_unique_constraints("eventos_reserva_outbox")})
                return
            resultado = await conn.run_sync(reparacion.reconciliar, copia)
            assert resultado["revision"] == reparacion.HEAD
            assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == reparacion.HEAD
            assert await conn.scalar(text("SELECT costo_reserva::text FROM reservas WHERE id=:id"), {"id": rid}) == "35.75"
            despues = await conn.run_sync(lambda c: huellas(c, {
                t.split(".")[1]: d["columns"] for t, d in copia["tables"].items()
                if not t.endswith(".alembic_version")}))
            for t, firma in despues.items():
                assert list(firma) == copia["tables"][db_usuarios.esquema + "." + t]["fingerprint"]
            assert await conn.scalar(text("SELECT count(*) FROM movimientos_fondo_moras")) == 0
            with pytest.raises(RuntimeError, match="marcador"):
                async with conn.begin_nested():
                    await conn.run_sync(reparacion.reconciliar, copia)
        finally:
            await transaction.rollback()


def test_rechaza_head_distinto(monkeypatch):
    monkeypatch.setattr(reparacion, "HEAD", "otra_revision")
    with pytest.raises(RuntimeError, match="head cambió"):
        reparacion.reconciliar(None, {})
