"""Fondos prospectivos y reservas: no importa cobros ni caja histórica."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261025_0020"
down_revision = "20261025_0019"
branch_labels = None
depends_on = None


def fk(nombre, tabla, nullable=False, **kw):
    return sa.Column(nombre, pg.UUID(as_uuid=True), sa.ForeignKey(f"{tabla}.id", ondelete="RESTRICT"), nullable=nullable, **kw)


def upgrade():
    op.create_table("cobros_mora_fondo",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("comprobante_id", "comprobantes_pago"), fk("cuota_id", "cuotas_mantenimiento"),
        fk("condominio_id", "condominios"), fk("edificio_id", "edificios"),
        sa.Column("moneda", sa.Text(), nullable=False),
        sa.Column("base_no_adoptada", sa.Numeric(12, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("comprobante_id", "cuota_id", name="uq_cobro_fondo_comprobante_cuota"),
        sa.CheckConstraint("base_no_adoptada >= 0", name="ck_cobro_fondo_base"),
        sa.CheckConstraint("moneda IN ('PEN','USD')", name="ck_cobro_fondo_moneda"))
    op.create_index("idx_cobro_fondo_cuota", "cobros_mora_fondo", ["cuota_id"])
    op.create_index("idx_cobro_fondo_ambito", "cobros_mora_fondo", ["condominio_id", "edificio_id", "moneda"])
    op.create_table("aplicaciones_fondo_moras",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("presupuesto_id", "presupuestos_mensuales"),
        sa.Column("item_id", pg.UUID(as_uuid=True), nullable=False),
        fk("edificio_id", "edificios"),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("clave_idempotencia", sa.Text(), nullable=False),
        sa.Column("version_solicitada", sa.Integer(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("presupuesto_id", "clave_idempotencia", name="uq_aplicacion_moras_clave"),
        sa.CheckConstraint("monto > 0 AND version_solicitada > 0", name="ck_aplicacion_moras_monto_version"),
        sa.CheckConstraint("estado IN ('RESERVADA','CONFIRMADA','LIBERADA')", name="ck_aplicacion_moras_estado"))
    op.create_index("idx_aplicacion_moras_edificio", "aplicaciones_fondo_moras", ["edificio_id"])
    op.create_table("movimientos_fondo_moras",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("condominio_id", "condominios"), fk("edificio_id", "edificios"),
        sa.Column("moneda", sa.Text(), nullable=False), sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("importe", sa.Numeric(12, 2), nullable=False),
        fk("cobro_id", "cobros_mora_fondo", nullable=True),
        fk("aplicacion_id", "aplicaciones_fondo_moras", nullable=True),
        fk("movimiento_diario_id", "movimientos_imputacion_diaria", nullable=True, unique=True),
        fk("imputacion_legacy_id", "imputaciones_pago", nullable=True, unique=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("aplicacion_id", "tipo", name="uq_mov_fondo_aplicacion_tipo"),
        sa.CheckConstraint("moneda IN ('PEN','USD')", name="ck_mov_fondo_moneda"),
        sa.CheckConstraint("(tipo = 'COBRO' AND cobro_id IS NOT NULL AND aplicacion_id IS NULL AND importe <> 0) OR "
            "(tipo = 'RESERVA' AND aplicacion_id IS NOT NULL AND cobro_id IS NULL AND importe < 0) OR "
            "(tipo = 'LIBERACION' AND aplicacion_id IS NOT NULL AND cobro_id IS NULL AND importe > 0)", name="ck_mov_fondo_tipo"))
    op.create_index("idx_mov_fondo_ambito", "movimientos_fondo_moras", ["condominio_id", "edificio_id", "moneda", "creado_en"])
    op.create_index("idx_mov_fondo_cobro", "movimientos_fondo_moras", ["cobro_id"])
    op.create_index("idx_mov_fondo_aplicacion", "movimientos_fondo_moras", ["aplicacion_id"])
    op.create_table("eventos_fondo_moras_outbox",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True), fk("edificio_id", "edificios"),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_evento_fondo_pendiente", "eventos_fondo_moras_outbox", ["publicado_en", "creado_en"])
    op.create_index("idx_evento_fondo_edificio", "eventos_fondo_moras_outbox", ["edificio_id"])
    for tabla in ("cobros_mora_fondo", "movimientos_fondo_moras"):
        op.execute(f"CREATE TRIGGER inmutable_{tabla} BEFORE UPDATE OR DELETE ON {tabla} "
                   "FOR EACH ROW EXECUTE FUNCTION proteger_ledger_diario()")
    op.execute("""CREATE FUNCTION proteger_aplicacion_moras() RETURNS trigger AS $$ BEGIN
        IF TG_OP = 'UPDATE' THEN
          IF OLD.estado = 'RESERVADA' AND NEW.estado IN ('CONFIRMADA','LIBERADA')
             AND (to_jsonb(NEW) - 'estado' - 'actualizado_en') = (to_jsonb(OLD) - 'estado' - 'actualizado_en')
             AND NEW.actualizado_en >= OLD.actualizado_en THEN RETURN NEW; END IF;
        END IF;
        RAISE EXCEPTION 'Aplicacion de moras inmutable: solo confirmar o liberar una reserva';
        END; $$ LANGUAGE plpgsql""")
    op.execute("CREATE TRIGGER proteger_aplicacion_moras BEFORE UPDATE OR DELETE ON aplicaciones_fondo_moras "
               "FOR EACH ROW EXECUTE FUNCTION proteger_aplicacion_moras()")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM cobros_mora_fondo)
        OR EXISTS (SELECT 1 FROM aplicaciones_fondo_moras) THEN
        RAISE EXCEPTION 'Hay fondos o aplicaciones; concilie antes del downgrade'; END IF; END $$""")
    for tabla in ("eventos_fondo_moras_outbox", "movimientos_fondo_moras", "aplicaciones_fondo_moras", "cobros_mora_fondo"):
        op.drop_table(tabla)
    op.execute("DROP FUNCTION proteger_aplicacion_moras()")
