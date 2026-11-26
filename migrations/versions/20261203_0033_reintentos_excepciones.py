"""Cola de reintentos sobre las resoluciones persistidas de CON-86."""

import sqlalchemy as sa
from alembic import op

revision = "20261203_0033"
down_revision = "20261202_0032"
branch_labels = None
depends_on = None

TABLA = "excepciones_resoluciones"


def upgrade():
    op.add_column(TABLA, sa.Column("nombre_job", sa.Text()))
    op.add_column(TABLA, sa.Column("resultado_job", sa.Text()))
    op.add_column(TABLA, sa.Column("inicio_job", sa.DateTime(timezone=True)))
    op.add_column(TABLA, sa.Column("fin_job", sa.DateTime(timezone=True)))
    op.create_index(
        "uq_excepcion_job_reintento",
        TABLA,
        ["excepcion_id"],
        unique=True,
        postgresql_where=sa.text("accion = 'REINTENTAR_JOB' AND nombre_job IS NOT NULL"),
    )
    op.create_index(
        "uq_excepcion_job_activo",
        TABLA,
        ["nombre_job"],
        unique=True,
        postgresql_where=sa.text("resultado_job IN ('EN_COLA', 'EN_CURSO')"),
    )


def downgrade():
    op.drop_index("uq_excepcion_job_activo", table_name=TABLA)
    op.drop_index("uq_excepcion_job_reintento", table_name=TABLA)
    op.drop_column(TABLA, "fin_job")
    op.drop_column(TABLA, "inicio_job")
    op.drop_column(TABLA, "resultado_job")
    op.drop_column(TABLA, "nombre_job")
