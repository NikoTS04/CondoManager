"""Crear configuración de distribución para CON-10.

Revision ID: 20261014_0003
Revises: 20261008_0002
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261014_0003"
down_revision: str | None = "20261008_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "configuraciones_distribucion",
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
        sa.Column("metodo", sa.String(20), nullable=False),
        sa.Column("actualizado_por", sa.String(100), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", name="uq_distribucion_condominio"),
        sa.CheckConstraint(
            "metodo IN ('POR_ALICUOTA', 'EQUITATIVA')", name="ck_distribucion_metodo"
        ),
    )


def downgrade() -> None:
    op.drop_table("configuraciones_distribucion")
