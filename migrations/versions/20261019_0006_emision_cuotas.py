"""Cuotas, lotes y outbox transaccional de CON-11; completar FK de CON-13."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261019_0006"
down_revision = "20261018_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cuotas_mantenimiento",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "departamento_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("periodo", sa.String(7), nullable=False),
        *[
            sa.Column(nombre, sa.Numeric(12, 2), nullable=False)
            for nombre in (
                "monto_ordinario",
                "monto_extraordinario",
                "monto_mora",
                "monto_descuento",
                "monto_total_exigible",
                "monto_pagado",
            )
        ],
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.UniqueConstraint("departamento_id", "periodo", name="uq_departamento_periodo"),
        *[
            sa.CheckConstraint(f"{nombre} >= 0.00", name=f"ck_cuota_{nombre}")
            for nombre in (
                "monto_ordinario",
                "monto_extraordinario",
                "monto_mora",
                "monto_descuento",
                "monto_total_exigible",
            )
        ],
        sa.CheckConstraint(
            "monto_pagado BETWEEN 0.00 AND monto_total_exigible", name="ck_cuota_monto_pagado"
        ),
        sa.CheckConstraint(
            "estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA')",
            name="ck_cuota_estado",
        ),
    )
    op.create_foreign_key(
        "fk_aplicacion_saldo_cuota",
        "aplicaciones_saldo_favor",
        "cuotas_mantenimiento",
        ["cuota_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "lotes_cuotas",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "condominio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "presupuesto_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("presupuestos_mensuales.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("periodo", sa.String(7), nullable=False),
        sa.Column("metodo", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(150), nullable=False),
        sa.Column("total_cuotas_emitidas", sa.Integer(), nullable=False),
        sa.Column("monto_total_facturado", sa.Numeric(12, 2), nullable=False),
        sa.Column("cuotas_cubiertas_saldo_favor", sa.Integer(), nullable=False),
        sa.Column("fecha_emision", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.UniqueConstraint("condominio_id", "periodo", name="uq_lote_condominio_periodo"),
        sa.CheckConstraint("monto_total_facturado > 0", name="ck_lote_monto"),
        sa.CheckConstraint("total_cuotas_emitidas > 0", name="ck_lote_cantidad"),
        sa.CheckConstraint("metodo IN ('POR_ALICUOTA', 'EQUITATIVA')", name="ck_lote_metodo"),
    )
    op.create_table(
        "eventos_lote_outbox",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lote_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("lotes_cuotas.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("eventos_lote_outbox")
    op.drop_table("lotes_cuotas")
    op.drop_constraint("fk_aplicacion_saldo_cuota", "aplicaciones_saldo_favor", type_="foreignkey")
    op.drop_table("cuotas_mantenimiento")
