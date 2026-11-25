"""Clasificación manual y rechazo de incidencias (CON-54)."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0024"
down_revision = "20261124_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incidencias", sa.Column("categoria_confirmada", sa.Text()))
    op.add_column("incidencias", sa.Column("prioridad", sa.Text()))
    op.add_column("incidencias", sa.Column("motivo_rechazo", sa.Text()))
    op.add_column(
        "incidencias", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_check_constraint("ck_incidencia_version", "incidencias", "version >= 1")
    op.create_check_constraint(
        "ck_incidencia_clasificacion",
        "incidencias",
        "(categoria_confirmada IS NULL) = (prioridad IS NULL)",
    )
    op.create_check_constraint(
        "ck_incidencia_prioridad",
        "incidencias",
        "prioridad IN ('BAJA', 'MEDIA', 'ALTA', 'URGENTE')",
    )
    op.create_check_constraint(
        "ck_incidencia_motivo_rechazo",
        "incidencias",
        "(estado = 'RECHAZADO') = (motivo_rechazo IS NOT NULL)",
    )


def downgrade():
    op.execute(
        "UPDATE incidencias SET estado = 'REGISTRADO', motivo_rechazo = NULL "
        "WHERE estado = 'RECHAZADO'"
    )
    for nombre in (
        "ck_incidencia_motivo_rechazo",
        "ck_incidencia_prioridad",
        "ck_incidencia_clasificacion",
        "ck_incidencia_version",
    ):
        op.drop_constraint(nombre, "incidencias", type_="check")
    for nombre in ("version", "motivo_rechazo", "prioridad", "categoria_confirmada"):
        op.drop_column("incidencias", nombre)
