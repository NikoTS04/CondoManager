"""Confirmación, calificación, cierre y reapertura de incidencias (CON-57)."""

import sqlalchemy as sa
from alembic import op

revision = "20261129_0029"
down_revision = "20261128_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incidencias", sa.Column("calificacion", sa.Integer(), nullable=True))
    op.add_column("incidencias", sa.Column("motivo_reapertura", sa.Text(), nullable=True))
    op.add_column(
        "incidencias", sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "incidencias",
        sa.Column(
            "cerrado_por",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_incidencia_calificacion",
        "incidencias",
        "calificacion IS NULL OR calificacion BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_incidencia_cierre",
        "incidencias",
        "(estado = 'CERRADO') = (fecha_cierre IS NOT NULL AND cerrado_por IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("ck_incidencia_cierre", "incidencias", type_="check")
    op.drop_constraint("ck_incidencia_calificacion", "incidencias", type_="check")
    op.drop_column("incidencias", "cerrado_por")
    op.drop_column("incidencias", "fecha_cierre")
    op.drop_column("incidencias", "motivo_reapertura")
    op.drop_column("incidencias", "calificacion")
