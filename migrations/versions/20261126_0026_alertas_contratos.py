"""Avisos de vencimiento de contratos (CON-50).

`contrato_id` no tiene llave foránea hasta que exista la tabla de contratos (CON-49).
La cadena enlaza con 20261125_0025 (alertas de fallos definitivos, CON-84).
"""

import sqlalchemy as sa
from alembic import op

revision = "20261126_0026"
down_revision = "20261125_0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "avisos_contrato",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "condominio_id",
            sa.Uuid(),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("vigencia", sa.Text(), nullable=False),
        sa.Column("umbral_dias", sa.Integer(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("prioridad", sa.Text(), nullable=False),
        sa.Column("destinatario_rol", sa.Text(), nullable=False, server_default="ADMIN_JUNTA"),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("dias_restantes", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("omitido_por_umbral", sa.Integer()),
        sa.Column("fecha_evaluacion", sa.Date(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "contrato_id", "vigencia", "umbral_dias", name="uq_aviso_contrato_umbral"
        ),
        sa.CheckConstraint("umbral_dias IN (60, 30)", name="ck_aviso_contrato_umbral"),
        sa.CheckConstraint("estado IN ('GENERADO', 'OMITIDO')", name="ck_aviso_contrato_estado"),
        sa.CheckConstraint(
            "prioridad IN ('INFORMATIVA', 'PRIORITARIA')", name="ck_aviso_contrato_prioridad"
        ),
        sa.CheckConstraint(
            "(estado = 'OMITIDO') = (omitido_por_umbral IS NOT NULL)",
            name="ck_aviso_contrato_omision",
        ),
        sa.CheckConstraint("dias_restantes >= 0", name="ck_aviso_contrato_dias"),
    )
    op.create_index(
        "ix_aviso_contrato_condominio", "avisos_contrato", ["condominio_id", "creado_en"]
    )


def downgrade():
    op.drop_index("ix_aviso_contrato_condominio", table_name="avisos_contrato")
    op.drop_table("avisos_contrato")
