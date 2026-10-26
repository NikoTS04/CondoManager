"""Catálogo y snapshots mensuales; no reconstruye ni modifica lotes históricos."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261025_0018"
down_revision = "20261024_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("conceptos_presupuestales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("condominio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("categoria", sa.String(40), nullable=False),
        sa.Column("descripcion", sa.String(500), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("condominio_id", "codigo", name="uq_concepto_condominio_codigo"),
    )
    op.add_column("presupuestos_mensuales", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("presupuestos_mensuales", sa.Column("items", postgresql.JSONB()))
    op.add_column("presupuestos_mensuales", sa.Column("prorrateo_snapshot", postgresql.JSONB()))
    op.add_column("cuotas_mantenimiento", sa.Column("detalle_prorrateo", postgresql.JSONB()))
    op.create_check_constraint("ck_presupuesto_version", "presupuestos_mensuales", "version > 0")
    op.drop_constraint("ck_presupuesto_monto_positivo", "presupuestos_mensuales", type_="check")
    op.create_check_constraint("ck_presupuesto_monto_positivo", "presupuestos_mensuales", "monto_total >= 0")
    op.drop_constraint("ck_lote_monto", "lotes_cuotas", type_="check")
    op.create_check_constraint("ck_lote_monto", "lotes_cuotas", "monto_total_facturado >= 0")
    op.drop_constraint("ck_lote_metodo", "lotes_cuotas", type_="check")
    op.create_check_constraint("ck_lote_metodo", "lotes_cuotas", "metodo IN ('POR_ALICUOTA','EQUITATIVA','JERARQUICA')")


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM presupuestos_mensuales WHERE items IS NOT NULL OR monto_total = 0) OR EXISTS (SELECT 1 FROM conceptos_presupuestales) OR EXISTS (SELECT 1 FROM lotes_cuotas WHERE metodo = 'JERARQUICA' OR monto_total_facturado = 0) THEN RAISE EXCEPTION 'Hay detalle financiero; concilie antes del downgrade'; END IF; END $$")
    op.drop_constraint("ck_lote_metodo", "lotes_cuotas", type_="check")
    op.create_check_constraint("ck_lote_metodo", "lotes_cuotas", "metodo IN ('POR_ALICUOTA','EQUITATIVA')")
    op.drop_constraint("ck_lote_monto", "lotes_cuotas", type_="check")
    op.create_check_constraint("ck_lote_monto", "lotes_cuotas", "monto_total_facturado > 0")
    op.drop_constraint("ck_presupuesto_monto_positivo", "presupuestos_mensuales", type_="check")
    op.create_check_constraint("ck_presupuesto_monto_positivo", "presupuestos_mensuales", "monto_total > 0")
    op.drop_constraint("ck_presupuesto_version", "presupuestos_mensuales", type_="check")
    op.drop_column("cuotas_mantenimiento", "detalle_prorrateo")
    for columna in ("prorrateo_snapshot", "items", "version"):
        op.drop_column("presupuestos_mensuales", columna)
    op.drop_table("conceptos_presupuestales")
