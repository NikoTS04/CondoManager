"""Crear presupuestos mensuales para CON-9.

Revision ID: 20261008_0002
Revises: 20261008_0001
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261008_0002"
down_revision: str | None = "20261008_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "presupuestos_mensuales",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "condominio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("moneda", sa.String(length=3), nullable=False),
        sa.Column("monto_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'BORRADOR'"),
        ),
        sa.Column("creado_por", sa.String(length=100), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("aprobado_por", sa.String(length=100), nullable=True),
        sa.Column("aprobado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "condominio_id",
            "periodo",
            name="uq_presupuesto_condominio_periodo",
        ),
        sa.CheckConstraint(
            "periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
            name="ck_presupuesto_periodo",
        ),
        sa.CheckConstraint(
            "moneda IN ('PEN', 'USD')",
            name="ck_presupuesto_moneda",
        ),
        sa.CheckConstraint(
            "monto_total > 0.00",
            name="ck_presupuesto_monto_positivo",
        ),
        sa.CheckConstraint(
            "CASE "
            "WHEN periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN "
            "EXTRACT(YEAR FROM fecha_vencimiento) = "
            "CAST(SUBSTRING(periodo FROM 1 FOR 4) AS INTEGER) "
            "AND EXTRACT(MONTH FROM fecha_vencimiento) = "
            "CAST(SUBSTRING(periodo FROM 6 FOR 2) AS INTEGER) "
            "ELSE FALSE END",
            name="ck_presupuesto_vencimiento_periodo",
        ),
        sa.CheckConstraint(
            "(estado = 'BORRADOR' AND aprobado_por IS NULL AND aprobado_en IS NULL) "
            "OR (estado = 'APROBADO' AND aprobado_por IS NOT NULL "
            "AND aprobado_en IS NOT NULL)",
            name="ck_presupuesto_aprobacion",
        ),
        sa.CheckConstraint(
            "estado IN ('BORRADOR', 'APROBADO')",
            name="ck_presupuesto_estado",
        ),
    )
    op.create_index(
        "idx_presupuestos_condominio_estado",
        "presupuestos_mensuales",
        ["condominio_id", "estado"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_presupuestos_condominio_estado",
        table_name="presupuestos_mensuales",
    )
    op.drop_table("presupuestos_mensuales")
