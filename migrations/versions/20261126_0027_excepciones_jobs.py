"""Decisiones y reintentos de excepciones globales de CON-66."""

import sqlalchemy as sa
from alembic import op

revision = "20261126_0027"
down_revision = "20261126_0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "excepciones_job_resoluciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "alerta_id",
            sa.Uuid(),
            sa.ForeignKey("notificaciones_alertas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nombre_job", sa.Text(), nullable=False),
        sa.Column("clave", sa.Uuid(), nullable=False),
        sa.Column("huella", sa.Text(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("responsable", sa.Text()),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resultado", sa.Text(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True)),
        sa.Column("fin", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("alerta_id", "clave", name="uq_excepcion_job_clave"),
        sa.CheckConstraint(
            "(accion = 'REINTENTAR_JOB' AND resultado IN "
            "('EN_COLA', 'EN_CURSO', 'COMPLETADO', 'FALLIDO', 'INCIERTO')) "
            "OR (accion = 'CERRAR_CON_MOTIVO' AND resultado = 'OMITIDO') "
            "OR (accion = 'SOLICITAR_INFORMACION' AND resultado = 'PENDIENTE_INFORMACION')",
            name="ck_excepcion_job_resultado",
        ),
        sa.CheckConstraint(
            "(accion = 'SOLICITAR_INFORMACION') = (responsable IS NOT NULL)",
            name="ck_excepcion_job_responsable",
        ),
    )
    op.create_index(
        "uq_excepcion_job_reintento",
        "excepciones_job_resoluciones",
        ["alerta_id"],
        unique=True,
        postgresql_where=sa.text("accion = 'REINTENTAR_JOB'"),
    )
    op.create_index(
        "uq_excepcion_job_activo",
        "excepciones_job_resoluciones",
        ["nombre_job"],
        unique=True,
        postgresql_where=sa.text(
            "accion = 'REINTENTAR_JOB' AND resultado IN ('EN_COLA', 'EN_CURSO')"
        ),
    )


def downgrade():
    op.drop_table("excepciones_job_resoluciones")
