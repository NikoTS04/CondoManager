"""Conservar asignaciones revocadas de roles contextuales (CON-06)."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0008"
down_revision = "20261020_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuario_roles",
        sa.Column("es_activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    # La revisión anterior no distingue una asignación revocada de una vigente.
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM usuario_roles WHERE NOT es_activo)")
    ):
        raise RuntimeError(
            "CON-06: existen roles revocados; la revisión anterior no preserva esa revocación."
        )
    op.drop_column("usuario_roles", "es_activo")
