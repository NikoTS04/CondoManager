"""Responsable por unidad, override y snapshot de nuevas cuotas; no inventa historia."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261024_0017"
down_revision = "20261024_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuario_departamentos", sa.Column("dias_gracia_override", sa.SmallInteger()))
    op.create_check_constraint(
        "ck_vinculo_gracia_override",
        "usuario_departamentos",
        "dias_gracia_override BETWEEN 0 AND 30",
    )
    op.add_column("departamentos", sa.Column("responsable_pago_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "departamentos",
        sa.Column("condiciones_pago_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        "fk_departamento_responsable_pago",
        "departamentos",
        "usuario_departamentos",
        ["responsable_pago_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_departamento_condiciones_version", "departamentos", "condiciones_pago_version > 0"
    )
    op.add_column("cuotas_mantenimiento", sa.Column("politica_mora_aplicada", postgresql.JSONB()))


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM departamentos WHERE condiciones_pago_version > 1) OR EXISTS (SELECT 1 FROM cuotas_mantenimiento WHERE politica_mora_aplicada IS NOT NULL) THEN RAISE EXCEPTION 'Existen condiciones de pago o snapshots; concilie antes del downgrade'; END IF; END $$"
    )
    op.drop_column("cuotas_mantenimiento", "politica_mora_aplicada")
    op.drop_constraint("ck_departamento_condiciones_version", "departamentos", type_="check")
    op.drop_constraint("fk_departamento_responsable_pago", "departamentos", type_="foreignkey")
    op.drop_column("departamentos", "responsable_pago_id")
    op.drop_column("departamentos", "condiciones_pago_version")
    op.drop_constraint("ck_vinculo_gracia_override", "usuario_departamentos", type_="check")
    op.drop_column("usuario_departamentos", "dias_gracia_override")
