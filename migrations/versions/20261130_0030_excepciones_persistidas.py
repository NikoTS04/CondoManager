"""Persistencia de excepciones y condominio centinela para auditoría global (CON-86)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261130_0030"
down_revision = "20261129_0029"
branch_labels = None
depends_on = None

CONDOMINIO_SISTEMA = "3709ed64-791a-5cd8-99c7-142ab3ee590c"


def upgrade():
    op.execute(
        f"""
        INSERT INTO condominios
            (id, nombre, direccion, moneda, regla_mora_tipo, monto_mora_fijo,
             dia_vencimiento, dias_gracia, politica_version, activo, creado_en)
        VALUES
            ('{CONDOMINIO_SISTEMA}', 'Sistema', 'Uso interno de auditoría', 'PEN',
             'MONTO_FIJO', 0, 1, 0, 1, false, now())
        ON CONFLICT (id) DO NOTHING
        """
    )

    op.create_table(
        "excepciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alerta_id", sa.Uuid(), nullable=False),
        sa.Column("notificacion_id", sa.Uuid(), nullable=True),
        sa.Column(
            "condominio_id",
            sa.Uuid(),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("origen", sa.Text(), nullable=False),
        sa.Column("operacion_id", sa.Text(), nullable=False),
        sa.Column("causa", sa.Text(), nullable=False),
        sa.Column("prioridad", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False, server_default="ABIERTA"),
        sa.Column("referencia_correlacion", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("alerta_id", name="uq_excepcion_alerta"),
    )
    op.create_table(
        "excepciones_resoluciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "excepcion_id",
            sa.Uuid(),
            sa.ForeignKey("excepciones.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("efecto", JSONB(), nullable=False),
        sa.Column("clave_idempotencia", sa.Uuid(), nullable=False),
        sa.Column("huella", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("excepcion_id", "clave_idempotencia", name="uq_resolucion_excepcion"),
    )
    op.create_index(
        "ix_excepciones_resoluciones_excepcion_id",
        "excepciones_resoluciones",
        ["excepcion_id"],
    )
    op.create_table(
        "excepciones_evidencias",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "excepcion_id",
            sa.Uuid(),
            sa.ForeignKey("excepciones.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("detalle", JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_excepciones_evidencias_excepcion_id", "excepciones_evidencias", ["excepcion_id"]
    )


def downgrade():
    op.drop_index("ix_excepciones_evidencias_excepcion_id", "excepciones_evidencias")
    op.drop_table("excepciones_evidencias")
    op.drop_index("ix_excepciones_resoluciones_excepcion_id", "excepciones_resoluciones")
    op.drop_table("excepciones_resoluciones")
    op.drop_table("excepciones")
    op.execute(
        f"DELETE FROM condominios WHERE id = '{CONDOMINIO_SISTEMA}' "
        "AND NOT EXISTS (SELECT 1 FROM auditoria_logs WHERE condominio_id = "
        f"'{CONDOMINIO_SISTEMA}')"
    )
