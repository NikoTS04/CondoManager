"""Adopción explícita del despliegue 0013 con cancelaciones ya presentes.

Requiere respaldo restaurado y ensayo; no modifica migraciones históricas.
"""

import argparse
import asyncio
import hashlib
import json
from importlib import import_module
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.reconciliar_esquema_legacy import huellas, validar_modelos
from src.core.config import settings
from src.modules.notificaciones.models import (
    AlertaNotificacion,  # noqa: F401
    EventoConsumido,
    IncidenciaEvento,
    IntentoNotificacion,
    Notificacion,
)
from src.modules.pagos.fondos_models import (  # noqa: F401
    AplicacionMoras,
    CobroMoraFondo,
    EventoFondoMorasOutbox,
    MovimientoFondoMoras,
)
from src.modules.pagos.models_mora import (  # noqa: F401
    AjusteDevengoMora,
    ConciliacionDiaria,
    DevengoMora,
    EventoMoraOutbox,
    MovimientoImputacionDiaria,
)
from src.modules.pagos.models_persistencia import ArchivoVoucher, RevisionPago
from src.modules.reservas.models import (
    BloqueoArea,
    CancelacionReserva,
    CobroReserva,
    EventoReservaOutbox,
    Reserva,
)

ORIGEN = "20261021_0013"
HEAD = "20261025_0020"
REVISIONES = (
    "20261021_0015_alertas_notificaciones",
    "20261024_0016_politica_mora_diaria",
    "20261024_0017_condiciones_pago",
    "20261025_0018_prorrateo_detallado",
    "20261025_0019_motor_mora_diaria",
    "20261025_0020_fondos_moras",
)
ADOPTADAS = (
    Reserva,
    CobroReserva,
    CancelacionReserva,
    EventoReservaOutbox,
    BloqueoArea,
    Notificacion,
    IntentoNotificacion,
    EventoConsumido,
    IncidenciaEvento,
    ArchivoVoucher,
    RevisionPago,
)


def verificar_copia(conn, antes):
    """Requiere que la base siga coincidiendo con el respaldo, incluidas las tablas archivadas."""
    quote = conn.dialect.identifier_preparer.quote_identifier
    for nombre, datos in antes["tables"].items():
        esquema, tabla = nombre.split(".")
        columnas = ",".join(quote(c) for c in datos["columns"])
        sql = f"""SELECT count(*), md5(coalesce(string_agg(fila::text, '' ORDER BY fila::text), ''))
            FROM (SELECT to_jsonb(x) fila FROM
              (SELECT {columnas} FROM {quote(esquema)}.{quote(tabla)}) x) h"""
        if list(conn.execute(sa.text(sql)).one()) != datos["fingerprint"]:
            raise RuntimeError(f"La base difiere del respaldo: {nombre}")


def reconciliar(conn, respaldo):
    grafo = ScriptDirectory.from_config(Config("alembic.ini"))
    if grafo.get_current_head() != HEAD:
        raise RuntimeError("El head cambió; requiere otro ensayo.")
    esperadas = [nombre[:13] for nombre in reversed(REVISIONES)]
    if [r.revision for r in grafo.iterate_revisions(HEAD, "20261021_0014")] != esperadas:
        raise RuntimeError("El grafo cambió; requiere otro ensayo.")
    conn.execute(sa.text("SET LOCAL lock_timeout = '10s'"))
    conn.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
    conn.execute(sa.text("SELECT pg_advisory_xact_lock(7320261026)"))
    inspector = sa.inspect(conn)
    nombres = inspector.get_table_names()
    quote = conn.dialect.identifier_preparer.quote
    conn.execute(
        sa.text(
            "LOCK TABLE "
            + ",".join(quote(t) for t in sorted(nombres))
            + " IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    if list(conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalars()) != [ORIGEN]:
        raise RuntimeError("Se requiere exclusivamente el marcador 20261021_0013.")
    verificar_copia(conn, respaldo)
    if "notificaciones_alertas" in nombres or "devengos_mora" in nombres:
        raise RuntimeError("Adopción parcial posterior a 0013; requiere revisión.")
    if conn.scalar(
        sa.text("""SELECT EXISTS (
        SELECT 1 FROM reservas r
        LEFT JOIN areas_comunes a ON a.id=r.area_id
        LEFT JOIN departamentos d ON d.id=r.departamento_id
        LEFT JOIN edificios e ON e.id=d.edificio_id
        LEFT JOIN cancelaciones_reserva c ON c.reserva_id=r.id
        LEFT JOIN usuarios u ON u.id=c.actor_id
        WHERE a.id IS NULL OR e.id IS NULL OR a.condominio_id<>e.condominio_id
          OR r.condominio_id<>a.condominio_id
          OR (r.estado='CANCELADA' AND (c.reserva_id IS NULL OR u.id IS NULL
              OR r.fecha_cancelacion IS DISTINCT FROM c.fecha_cancelacion
              OR r.cancelado_por IS DISTINCT FROM c.actor_id
              OR r.motivo_cancelacion IS DISTINCT FROM c.motivo))
          OR (r.estado<>'CANCELADA' AND c.reserva_id IS NOT NULL))""")
    ):
        raise RuntimeError("Reservas sin contexto o evidencia verificable de cancelación.")
    # shortcut: no hay cobros de reserva en este incidente; otro estado exige nuevo ensayo financiero.
    if conn.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM cobros_reserva)")):
        raise RuntimeError("Cobros de reserva presentes; requiere conciliación específica.")
    if conn.scalar(
        sa.text("""SELECT EXISTS (SELECT 1 FROM eventos_reserva_outbox
        WHERE tipo IS NULL OR tipo IS DISTINCT FROM payload->>'event_type')
        OR EXISTS (SELECT 1 FROM eventos_reserva_outbox GROUP BY reserva_id,tipo HAVING count(*)>1)""")
    ):
        raise RuntimeError("Eventos sin tipo verificable o duplicados; no se reescribe historia.")
    tablas = {
        t: [c["name"] for c in inspector.get_columns(t)] for t in nombres if t != "alembic_version"
    }
    antes = huellas(conn, tablas)
    rls = dict(
        conn.execute(
            sa.text("""SELECT c.relname,c.relrowsecurity FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=current_schema() AND c.relkind='r'""")
        ).all()
    )
    conn.execute(
        sa.text("""ALTER TABLE eventos_reserva_outbox
        ALTER COLUMN tipo SET NOT NULL,
        ALTER COLUMN tipo SET DEFAULT 'ReservaCanceladaEvent'""")
    )
    unicas = inspector.get_unique_constraints("eventos_reserva_outbox")
    if not any(c["column_names"] == ["reserva_id", "tipo"] for c in unicas):
        conn.execute(
            sa.text("""ALTER TABLE eventos_reserva_outbox
            ADD CONSTRAINT uq_evento_reserva_tipo UNIQUE (reserva_id,tipo)""")
        )
    validar_modelos(conn, [m.__table__ for m in ADOPTADAS])
    with Operations.context(MigrationContext.configure(conn)):
        for nombre in REVISIONES:
            import_module("migrations.versions." + nombre).upgrade()
    for tabla in set(sa.inspect(conn).get_table_names()) - set(nombres):
        conn.execute(sa.text(f"ALTER TABLE {quote(tabla)} ENABLE ROW LEVEL SECURITY"))
    validar_modelos(conn)
    if antes != huellas(conn, tablas):
        raise RuntimeError("Cambió una columna histórica; reparación revertida.")
    for tabla, protegido in rls.items():
        if protegido and not conn.scalar(
            sa.text("""SELECT c.relrowsecurity FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=current_schema() AND c.relname=:tabla"""),
            {"tabla": tabla},
        ):
            raise RuntimeError(f"Se perdió RLS: {tabla}")
    conn.execute(
        sa.text("UPDATE alembic_version SET version_num=:head WHERE version_num=:origen"),
        {"head": HEAD, "origen": ORIGEN},
    )
    return {"revision": HEAD, "tablas_preservadas": len(tablas)}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--respaldo", type=Path, required=True)
    args = parser.parse_args()
    if not args.aplicar:
        parser.error("Confirme respaldo restaurado y ensayo con --aplicar.")
    manifiesto = json.loads((args.respaldo / "sha256.json").read_text())
    for nombre in ("public.dump", "vouchers.tar.gz", "before.json"):
        if hashlib.sha256((args.respaldo / nombre).read_bytes()).hexdigest() != manifiesto[nombre]:
            raise RuntimeError(f"Respaldo alterado: {nombre}")
    respaldo = json.loads((args.respaldo / "before.json").read_text())
    engine = create_async_engine(settings.DATABASE_URL, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            resultado = await conn.run_sync(reconciliar, respaldo)
        print(resultado)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
