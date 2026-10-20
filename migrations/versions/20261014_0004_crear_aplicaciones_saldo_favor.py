"""Crear evidencia idempotente de aplicaciones de saldo a favor (CON-13)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261014_0004"
down_revision = "20261014_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CON-11 todavía no crea cuotas_mantenimiento. Su migración debe añadir
    # fk_aplicacion_saldo_cuota (cuota_id -> cuotas_mantenimiento.id, RESTRICT).
    # Se difiere solo la FK para permitir upgrade head antes de CON-11.
    op.create_table(
        "aplicaciones_saldo_favor",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cuota_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("saldo_previo", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_aplicado", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_pendiente", sa.Numeric(12, 2), nullable=False),
        sa.Column("saldo_restante", sa.Numeric(12, 2), nullable=False),
        sa.Column("estado_anterior", sa.String(20), nullable=False),
        sa.Column("estado_posterior", sa.String(20), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("cuota_id", name="uq_aplicacion_saldo_cuota"),
        sa.CheckConstraint(
            "saldo_previo >= 0 AND monto_aplicado >= 0 AND monto_pendiente >= 0 "
            "AND saldo_restante >= 0 AND saldo_previo = monto_aplicado + saldo_restante",
            name="ck_aplicacion_saldo_importes",
        ),
        sa.CheckConstraint(
            "estado_anterior = 'EMITIDA' AND "
            "((estado_posterior = 'PAGADA' AND monto_pendiente = 0) OR "
            "(estado_posterior = 'PENDIENTE' AND monto_pendiente > 0))",
            name="ck_aplicacion_saldo_estados",
        ),
    )


def downgrade() -> None:
    op.drop_table("aplicaciones_saldo_favor")
