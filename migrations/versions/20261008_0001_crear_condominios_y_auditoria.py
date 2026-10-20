"""Crear condominios y auditoría para CON-2.

Revision ID: 20261008_0001
Revises: None
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261008_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "condominios",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("direccion", sa.Text(), nullable=False),
        sa.Column("moneda", sa.String(length=3), nullable=False),
        sa.Column("regla_mora_tipo", sa.String(length=20), nullable=False),
        sa.Column("monto_mora_fijo", sa.Numeric(12, 2), nullable=True),
        sa.Column("tasa_mora_porcentaje", sa.Numeric(7, 4), nullable=True),
        sa.Column("dia_vencimiento", sa.SmallInteger(), nullable=False),
        sa.Column("dias_gracia", sa.SmallInteger(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("moneda IN ('PEN', 'USD')", name="ck_condominio_moneda"),
        sa.CheckConstraint(
            "regla_mora_tipo IN ('MONTO_FIJO', 'PORCENTAJE_SALDO')",
            name="ck_condominio_regla_mora",
        ),
        sa.CheckConstraint(
            "dia_vencimiento BETWEEN 1 AND 28",
            name="ck_condominio_dia_vencimiento",
        ),
        sa.CheckConstraint("dias_gracia BETWEEN 0 AND 30", name="ck_condominio_dias_gracia"),
        sa.CheckConstraint(
            "(regla_mora_tipo = 'MONTO_FIJO' "
            "AND monto_mora_fijo IS NOT NULL "
            "AND tasa_mora_porcentaje IS NULL) "
            "OR (regla_mora_tipo = 'PORCENTAJE_SALDO' "
            "AND tasa_mora_porcentaje IS NOT NULL "
            "AND monto_mora_fijo IS NULL)",
            name="ck_condominio_configuracion_mora",
        ),
    )

    op.create_table(
        "auditoria_logs",
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
        sa.Column("departamento_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("accion_ejecutada", sa.String(length=100), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        sa.Column("actor_tipo", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column(
            "estado_anterior",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "estado_posterior",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("hash_actual", sa.String(length=64), nullable=False),
        sa.Column("hash_previo", sa.String(length=64), nullable=True),
        sa.CheckConstraint("resultado IN ('EXITOSO', 'FALLIDO')", name="ck_auditoria_resultado"),
    )
    op.create_index(
        "idx_auditoria_condominio_fecha",
        "auditoria_logs",
        ["condominio_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("idx_auditoria_condominio_fecha", table_name="auditoria_logs")
    op.drop_table("auditoria_logs")
    op.drop_table("condominios")
