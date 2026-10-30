"""Indexar titulares activos sin reescribir tenencias históricas (CON-05)."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0009"
down_revision = "20261020_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "idx_vinculos_titulares_activos",
        "usuario_departamentos",
        ["departamento_id", "tipo_relacion"],
        postgresql_where=sa.text("es_activo IS TRUE"),
    )


def downgrade():
    op.drop_index("idx_vinculos_titulares_activos", table_name="usuario_departamentos")
