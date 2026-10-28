"""Reparación explícita y transaccional del despliegue 20261021_0012.

Ensayar sobre un respaldo restaurado antes de usar --aplicar en el despliegue.
No hace seeds, no publica eventos y no modifica migraciones históricas.
"""

import argparse
import asyncio
from importlib import import_module

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import settings
from src.core.database import Base
from src.core.models_audit import AuditoriaLogORM  # noqa: F401
from src.modules.condominios.models import Condominio  # noqa: F401
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion  # noqa: F401
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox, LoteCuotas  # noqa: F401
from src.modules.cuotas.presupuestos.models import PresupuestoMensual  # noqa: F401
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor  # noqa: F401
from src.modules.notificaciones.models import (
    EventoConsumido,
    IncidenciaEvento,
    IntentoNotificacion,
    Notificacion,
)
from src.modules.pagos.models import ComprobantePago, ImputacionPago  # noqa: F401
from src.modules.pagos.models_persistencia import (  # noqa: F401
    ArchivoVoucher,
    EventoPagoOutbox,
    RevisionPago,
)
from src.modules.reservas.models import BloqueoArea, Reserva  # noqa: F401
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol  # noqa: F401

LEGACY = "20261021_0012"
HEAD = "20261021_0015"
NUEVAS = (BloqueoArea, Notificacion, IntentoNotificacion, EventoConsumido, IncidenciaEvento)


def huellas(conn, tablas, archivo_notificaciones=None):
    """Compara columnas originales sin guardar datos personales ni convertir dinero."""
    quote = conn.dialect.identifier_preparer.quote
    result = {}
    for tabla, columnas in tablas.items():
        campos = ", ".join(quote(c) for c in columnas)
        origen = quote(tabla)
        if tabla == "notificaciones_logs" and archivo_notificaciones:
            origen = quote(archivo_notificaciones) + "." + origen
        sql = f"""SELECT count(*), md5(coalesce(string_agg(fila::text, '' ORDER BY fila::text), ''))
            FROM (SELECT to_jsonb(x) fila FROM
              (SELECT {campos} FROM {origen}) x) h"""
        result[tabla] = tuple(conn.execute(sa.text(sql)).one())
    return result


def validar_modelos(conn, tablas=None):
    inspector = sa.inspect(conn)
    for tabla in Base.metadata.sorted_tables if tablas is None else tablas:
        columnas = {c["name"]: c for c in inspector.get_columns(tabla.name)}
        for columna in tabla.columns:
            actual = columnas.get(columna.name)
            if (
                actual is None
                or actual["type"].compile(dialect=conn.dialect)
                != columna.type.compile(dialect=conn.dialect)
                or actual["nullable"] != columna.nullable
            ):
                raise RuntimeError(f"Esquema incompatible: {tabla.name}.{columna.name}")
        if inspector.get_pk_constraint(tabla.name)["constrained_columns"] != [c.name for c in tabla.primary_key]:
            raise RuntimeError(f"PK incompatible: {tabla.name}")
        fks = inspector.get_foreign_keys(tabla.name)
        checks = {c["name"] for c in inspector.get_check_constraints(tabla.name)}
        unicas = [c["column_names"] for c in inspector.get_unique_constraints(tabla.name)]
        for constraint in tabla.constraints:
            if isinstance(constraint, sa.ForeignKeyConstraint) and not any(
                f["constrained_columns"] == [e.parent.name for e in constraint.elements]
                and f["referred_table"] == constraint.referred_table.name
                and f["referred_columns"] == [e.column.name for e in constraint.elements]
                and f.get("options", {}).get("ondelete") == constraint.ondelete
                for f in fks
            ):
                raise RuntimeError(f"FK incompatible: {tabla.name}")
            if isinstance(constraint, sa.CheckConstraint) and constraint.name not in checks:
                raise RuntimeError(f"Check ausente: {tabla.name}.{constraint.name}")
            if isinstance(constraint, sa.UniqueConstraint) and [c.name for c in constraint.columns] not in unicas:
                raise RuntimeError(f"Unicidad ausente: {tabla.name}")


def reconciliar(conn):
    # shortcut: reparación ligada al head 0013; con otro head se requiere un ensayo nuevo.
    if ScriptDirectory.from_config(Config("alembic.ini")).get_current_head() != HEAD:
        raise RuntimeError("El head cambió; revisar y ensayar de nuevo esta reparación.")
    conn.execute(sa.text("SET LOCAL lock_timeout = '10s'"))
    conn.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
    conn.execute(sa.text("SELECT pg_advisory_xact_lock(7320210012)"))
    inspector = sa.inspect(conn)
    nombres = inspector.get_table_names()
    quote = conn.dialect.identifier_preparer.quote
    conn.execute(sa.text("LOCK TABLE " + ", ".join(quote(t) for t in sorted(nombres)) + " IN SHARE ROW EXCLUSIVE MODE"))
    revisiones = list(conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalars())
    if revisiones != [LEGACY]:
        raise RuntimeError("Se requiere exclusivamente el marcador legacy 20261021_0012.")
    if conn.scalar(sa.text("SELECT count(*) FROM notificaciones_logs")):
        raise RuntimeError("Notificaciones legacy no vacías: no se puede inventar identidad o entrega.")
    if conn.scalar(sa.text("SELECT count(*) FROM cobros_reserva")):
        raise RuntimeError("Hay cobros de reserva: conciliar su compensación antes de migrar.")
    for modelo in NUEVAS:
        if modelo is not Notificacion and modelo.__tablename__ in nombres:
            raise RuntimeError("Estructura parcialmente adoptada; requiere revisión manual.")
    if "condominio_id" in {c["name"] for c in inspector.get_columns("reservas")}:
        raise RuntimeError("Reservas parcialmente adoptadas; requiere revisión manual.")
    invalidas = conn.scalar(sa.text("""SELECT EXISTS (
        SELECT 1 FROM reservas r
        LEFT JOIN areas_comunes a ON a.id=r.area_id
        LEFT JOIN departamentos d ON d.id=r.departamento_id
        LEFT JOIN edificios e ON e.id=d.edificio_id
        LEFT JOIN cancelaciones_reserva c ON c.reserva_id=r.id
        LEFT JOIN usuarios u ON u.id=c.actor_id
        WHERE a.id IS NULL OR e.id IS NULL OR a.condominio_id<>e.condominio_id
           OR (r.estado='CANCELADA' AND (c.reserva_id IS NULL OR u.id IS NULL
               OR c.fecha_cancelacion IS NULL OR c.motivo IS NULL))
           OR (r.estado<>'CANCELADA' AND c.reserva_id IS NOT NULL))"""))
    if invalidas:
        raise RuntimeError("Reservas sin contexto o evidencia verificable de cancelación.")
    if conn.scalar(sa.text("""SELECT EXISTS (
        SELECT 1 FROM reservas a JOIN reservas b ON a.id<b.id
        AND a.area_id=b.area_id AND a.fecha_reserva=b.fecha_reserva
        WHERE a.estado='CONFIRMADA' AND b.estado='CONFIRMADA'
        AND a.hora_inicio<b.hora_fin AND b.hora_inicio<a.hora_fin)""")):
        raise RuntimeError("Reservas confirmadas solapadas; conciliar antes de migrar.")

    tablas = {t: [c["name"] for c in inspector.get_columns(t)] for t in nombres if t != "alembic_version"}
    antes = huellas(conn, tablas)
    archivo = conn.scalar(sa.text("SELECT current_schema()")) + "_legacy_20261021"
    conn.execute(sa.text(f"CREATE SCHEMA {quote(archivo)}"))
    conn.execute(sa.text(f"REVOKE ALL ON SCHEMA {quote(archivo)} FROM PUBLIC"))
    conn.execute(sa.text(f"ALTER TABLE notificaciones_logs SET SCHEMA {quote(archivo)}"))
    for modelo in NUEVAS:
        modelo.__table__.create(conn)
        conn.execute(sa.text(f"ALTER TABLE {quote(modelo.__tablename__)} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE bloqueos_area ALTER COLUMN activo SET DEFAULT true"))
    conn.execute(sa.text("""ALTER TABLE reservas
        ADD COLUMN condominio_id UUID REFERENCES condominios(id) ON DELETE RESTRICT,
        ADD COLUMN moneda VARCHAR(3), ADD COLUMN area_nombre TEXT,
        ADD COLUMN fecha_cancelacion TIMESTAMPTZ,
        ADD COLUMN cancelado_por UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
        ADD COLUMN motivo_cancelacion TEXT,
        ALTER COLUMN usuario_id DROP NOT NULL,
        ALTER COLUMN zona_horaria TYPE VARCHAR(40)"""))
    conn.execute(sa.text("""UPDATE reservas r SET condominio_id=a.condominio_id,
        moneda=c.moneda, area_nombre=a.nombre
        FROM areas_comunes a JOIN condominios c ON c.id=a.condominio_id WHERE a.id=r.area_id"""))
    conn.execute(sa.text("""UPDATE reservas r SET fecha_cancelacion=c.fecha_cancelacion,
        cancelado_por=c.actor_id, motivo_cancelacion=c.motivo
        FROM cancelaciones_reserva c WHERE c.reserva_id=r.id AND r.estado='CANCELADA'"""))
    conn.execute(sa.text("""ALTER TABLE reservas
        ALTER COLUMN condominio_id SET NOT NULL, ALTER COLUMN moneda SET NOT NULL,
        ALTER COLUMN area_nombre SET NOT NULL,
        ADD CONSTRAINT ck_reserva_moneda CHECK (moneda IN ('PEN','USD'))"""))
    conn.execute(sa.text("CREATE INDEX idx_reservas_contexto_unidad ON reservas (condominio_id, departamento_id)"))
    conn.execute(sa.text("ALTER INDEX idx_reservas_area_fecha RENAME TO idx_reservas_area_fecha_legacy"))
    conn.execute(sa.text("CREATE INDEX idx_reservas_area_fecha ON reservas (area_id, fecha_reserva, estado)"))
    conn.execute(sa.text("CREATE INDEX ix_eventos_reserva_outbox_reserva_id ON eventos_reserva_outbox (reserva_id)"))
    with Operations.context(MigrationContext.configure(conn)):
        import_module("migrations.versions.20261021_0013_convergencia_con72").upgrade()
        # 0014 solo une ramas sin DDL; 0015 crea notificaciones_alertas sobre las tablas nuevas.
        import_module("migrations.versions.20261021_0015_alertas_notificaciones").upgrade()
    validar_modelos(conn)
    if antes != huellas(conn, tablas, archivo):
        raise RuntimeError("Cambió una columna histórica; reparación revertida.")
    conn.execute(sa.text("UPDATE alembic_version SET version_num=:head WHERE version_num=:legacy"), {"head": HEAD, "legacy": LEGACY})
    return {"revision": HEAD, "tablas_preservadas": len(tablas), "archivo_legacy": archivo}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="Confirma respaldo restaurado y ensayo previo satisfactorio.")
    if not parser.parse_args().aplicar:
        parser.error("Primero respalde y ensaye en una copia; después use --aplicar.")
    engine = create_async_engine(settings.DATABASE_URL, echo=False, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            resultado = await conn.run_sync(reconciliar)
        print(resultado)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
