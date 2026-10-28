"""Ledger prospectivo; nunca atribuye políticas nuevas a cuotas o pagos históricos."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261025_0019"
down_revision = "20261025_0018"
branch_labels = None
depends_on = None


def fk(nombre, tabla, nullable=False):
    return sa.Column(nombre, pg.UUID(as_uuid=True), sa.ForeignKey(f"{tabla}.id", ondelete="RESTRICT"), nullable=nullable)


def upgrade():
    op.create_table("conciliaciones_diarias",
        sa.Column("comprobante_id", pg.UUID(as_uuid=True), sa.ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("cuotas_evaluadas", pg.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False))
    op.create_table("devengos_mora",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("cuota_id", "cuotas_mantenimiento"),
        sa.Column("fecha_local", sa.Date(), nullable=False),
        sa.Column("importe", sa.Numeric(12, 2), nullable=False),
        sa.Column("politica", pg.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("cuota_id", "fecha_local", name="uq_devengo_cuota_fecha"),
        sa.CheckConstraint("importe > 0", name="ck_devengo_importe"))
    op.create_table("ajustes_devengo_mora",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("devengo_id", "devengos_mora"),
        sa.Column("importe", sa.Numeric(12, 2), nullable=False),
        fk("comprobante_causante_id", "comprobantes_pago", nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("importe <> 0", name="ck_ajuste_devengo_importe"))
    op.create_index("idx_ajuste_devengo", "ajustes_devengo_mora", ["devengo_id"])
    op.create_table("movimientos_imputacion_diaria",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("comprobante_id", "comprobantes_pago"),
        fk("cuota_id", "cuotas_mantenimiento", nullable=True),
        sa.Column("componente", sa.String(20), nullable=False),
        sa.Column("importe", sa.Numeric(12, 2), nullable=False),
        fk("comprobante_causante_id", "comprobantes_pago", nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("importe <> 0", name="ck_mov_diario_importe"),
        sa.CheckConstraint("componente IN ('MORA','EXTRAORDINARIA','ORDINARIA','CREDITO')", name="ck_mov_diario_componente"),
        sa.CheckConstraint("(componente = 'CREDITO') = (cuota_id IS NULL)", name="ck_mov_diario_destino"))
    op.create_index("idx_mov_diario_comprobante", "movimientos_imputacion_diaria", ["comprobante_id"])
    op.create_index("idx_mov_diario_cuota", "movimientos_imputacion_diaria", ["cuota_id"])
    op.create_table("eventos_mora_outbox",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        fk("cuota_id", "cuotas_mantenimiento"),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_evento_mora_pendiente", "eventos_mora_outbox", ["publicado_en", "creado_en"])
    op.execute("""CREATE FUNCTION proteger_ledger_diario() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'El ledger diario es inmutable; registre una compensacion'; END;
        $$ LANGUAGE plpgsql""")
    for tabla in ("conciliaciones_diarias", "devengos_mora", "ajustes_devengo_mora", "movimientos_imputacion_diaria"):
        op.execute(f"CREATE TRIGGER inmutable_{tabla} BEFORE UPDATE OR DELETE ON {tabla} "
                   "FOR EACH ROW EXECUTE FUNCTION proteger_ledger_diario()")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM devengos_mora)
        OR EXISTS (SELECT 1 FROM conciliaciones_diarias)
        OR EXISTS (SELECT 1 FROM cuotas_mantenimiento WHERE politica_mora_aplicada->>'modalidad' = 'MONTO_DIARIO')
        THEN RAISE EXCEPTION 'Hay operaciones diarias; concilie antes del downgrade'; END IF; END $$""")
    for tabla in ("eventos_mora_outbox", "movimientos_imputacion_diaria", "ajustes_devengo_mora", "devengos_mora", "conciliaciones_diarias"):
        op.drop_table(tabla)
    op.execute("DROP FUNCTION proteger_ledger_diario()")
