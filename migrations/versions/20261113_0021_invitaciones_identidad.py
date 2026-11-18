"""CON-76: invitaciones y finalidades de correo, conservando cuentas existentes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261113_0021"
down_revision = "20261025_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("activacion_pendiente", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "invitaciones_usuario",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "condominio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "creador_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("revision_cuenta", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilizada_en", sa.DateTime(timezone=True)),
        sa.Column("revocada_en", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "expira_en > creado_en AND revision_cuenta >= 1", name="ck_invitacion_fechas"
        ),
    )
    op.create_index("idx_invitacion_usuario", "invitaciones_usuario", ["usuario_id"])
    op.create_table(
        "operaciones_identidad",
        sa.Column(
            "condominio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("clave", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("respuesta", pg.JSONB(), nullable=False),
    )
    op.alter_column("notificaciones_logs", "departamento_id", nullable=True)
    op.alter_column("notificaciones_alertas", "departamento_id", nullable=True)
    op.add_column(
        "notificaciones_logs",
        sa.Column("finalidad", sa.String(20), nullable=False, server_default="OPERATIVA"),
    )
    op.add_column("notificaciones_logs", sa.Column("contenido_cifrado", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_notificacion_finalidad",
        "notificaciones_logs",
        "(finalidad = 'OPERATIVA' AND departamento_id IS NOT NULL AND contenido_cifrado IS NULL) OR finalidad IN ('INVITACION','SEGURIDAD')",
    )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM invitaciones_usuario)
        OR EXISTS (SELECT 1 FROM operaciones_identidad)
        OR EXISTS (SELECT 1 FROM notificaciones_logs WHERE finalidad <> 'OPERATIVA') THEN
        RAISE EXCEPTION 'Hay identidad o avisos persistidos; no se puede perder su historial';
        END IF; END $$""")
    op.drop_constraint("ck_notificacion_finalidad", "notificaciones_logs")
    op.drop_column("notificaciones_logs", "contenido_cifrado")
    op.drop_column("notificaciones_logs", "finalidad")
    op.alter_column("notificaciones_logs", "departamento_id", nullable=False)
    op.alter_column("notificaciones_alertas", "departamento_id", nullable=False)
    op.drop_table("operaciones_identidad")
    op.drop_table("invitaciones_usuario")
    op.drop_column("usuarios", "activacion_pendiente")
