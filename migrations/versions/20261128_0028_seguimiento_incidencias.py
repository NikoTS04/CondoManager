"""Seguimiento, evidencias, costos e historial de incidencias (CON-56)."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_0028"
down_revision = "20261127_0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incidencias_actualizaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "condominio_id",
            sa.Uuid(),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "incidencia_id",
            sa.Uuid(),
            sa.ForeignKey("incidencias.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("publico", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("repuesto", sa.Text(), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=True),
        sa.Column("estado_anterior", sa.Text(), nullable=True),
        sa.Column("estado_nuevo", sa.Text(), nullable=True),
        sa.Column("evidencia", sa.LargeBinary(), nullable=True),
        sa.Column("evidencia_mime", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "tipo IN ('COMENTARIO','CAMBIO_ESTADO','COSTO')", name="ck_actualizacion_tipo"
        ),
        sa.CheckConstraint("monto IS NULL OR monto >= 0", name="ck_actualizacion_monto"),
        sa.CheckConstraint(
            "estado_nuevo IS NULL OR estado_nuevo IN "
            "('REGISTRADO','ASIGNADO','EN_PROCESO','RESUELTO','CERRADO','RECHAZADO')",
            name="ck_actualizacion_estado",
        ),
    )
    op.create_index(
        "ix_incidencias_actualizaciones_incidencia_id",
        "incidencias_actualizaciones",
        ["incidencia_id"],
    )


def downgrade():
    op.drop_index("ix_incidencias_actualizaciones_incidencia_id", "incidencias_actualizaciones")
    op.drop_table("incidencias_actualizaciones")
