"""CON-37: alertas administrativas por fallos permanentes de notificación."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261021_0015"
down_revision = "20261021_0014"
branch_labels = None
depends_on = None

TIPOS = (
    "ERROR_DEFINITIVO",
    "INTENTOS_AGOTADOS",
    "ACEPTACION_INCIERTA",
    "DESTINATARIO_INVALIDO",
    "PROVEEDOR_NO_CONFIGURADO",
)


def upgrade():
    op.create_table(
        "notificaciones_alertas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "notificacion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notificaciones_logs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "condominio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "departamento_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atendida_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "atendida_por",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.UniqueConstraint("notificacion_id", "ciclo", "tipo", name="uq_alerta_notificacion_tipo"),
        sa.CheckConstraint("tipo IN ('" + "','".join(TIPOS) + "')", name="ck_alerta_tipo"),
        sa.CheckConstraint(
            "(atendida_en IS NULL) = (atendida_por IS NULL)", name="ck_alerta_atencion"
        ),
    )
    op.create_index(
        "idx_alerta_abierta",
        "notificaciones_alertas",
        ["condominio_id", "creada_en"],
        postgresql_where=sa.text("atendida_en IS NULL"),
    )
    op.execute("ALTER TABLE notificaciones_alertas ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_index("idx_alerta_abierta", table_name="notificaciones_alertas")
    op.drop_table("notificaciones_alertas")
