"""Registro de incidencias de residentes y evidencia privada."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0023"
down_revision = "20261121_0022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incidencias",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "condominio_id",
            sa.Uuid(),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reportante_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "departamento_id",
            sa.Uuid(),
            sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("clave_idempotencia", sa.Uuid(), nullable=False),
        sa.Column("hash_solicitud", sa.Text(), nullable=False),
        sa.Column("ubicacion", sa.Text(), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("urgencia", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="REGISTRADO", nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("evidencia", sa.LargeBinary()),
        sa.Column("evidencia_mime", sa.Text()),
        sa.UniqueConstraint(
            "condominio_id", "reportante_id", "clave_idempotencia", name="uq_incidencia_operacion"
        ),
    )
    op.create_index("ix_incidencias_reportante_id", "incidencias", ["reportante_id"])
    op.create_index("ix_incidencias_departamento_id", "incidencias", ["departamento_id"])


def downgrade():
    op.drop_table("incidencias")
