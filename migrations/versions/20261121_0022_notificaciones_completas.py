"""Cierre EMAIL: borradores, políticas, supresión, outbox y supervisión."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20261121_0022"
down_revision = "20261113_0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notificaciones_logs", sa.Column("recordatorio_vencimiento", sa.Date()))
    op.add_column("notificaciones_logs", sa.Column("recordatorio_dias", sa.Integer()))
    op.create_table(
        "comunicados",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("condominio_id", UUID(as_uuid=True), sa.ForeignKey("condominios.id"), nullable=False),
        sa.Column("contenido", JSONB, nullable=False),
        sa.Column("audiencia", JSONB, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmado_en", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_comunicados_condominio_id", "comunicados", ["condominio_id"])
    op.create_table(
        "politicas_notificaciones",
        sa.Column("condominio_id", UUID(as_uuid=True), sa.ForeignKey("condominios.id"), primary_key=True),
        sa.Column("dias", JSONB, nullable=False),
        sa.Column("hora", sa.Integer(), nullable=False),
        sa.Column("habilitado", sa.Boolean(), nullable=False),
        sa.Column("ultima_fecha", sa.Date()),
        sa.CheckConstraint("hora BETWEEN 0 AND 23", name="ck_notificaciones_hora"),
    )
    op.create_table(
        "contactos_bloqueados",
        sa.Column("condominio_id", UUID(as_uuid=True), sa.ForeignKey("condominios.id"), primary_key=True),
        sa.Column("email", sa.Text(), primary_key=True),
        sa.Column("motivo", sa.String(30), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "eventos_solvencia_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("comprobante_id", UUID(as_uuid=True),
                  sa.ForeignKey("comprobantes_pago.id"), nullable=False, unique=True),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_table(
        "estado_job_notificaciones",
        sa.Column("nombre", sa.String(30), primary_key=True),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True)),
        sa.Column("estado", sa.String(30), nullable=False),
    )
    # Tablas internas: el propietario SQL opera; PostgREST público no accede sin políticas.
    for tabla in (
        "comunicados", "politicas_notificaciones", "contactos_bloqueados",
        "eventos_solvencia_outbox", "estado_job_notificaciones",
    ):
        op.execute(f'ALTER TABLE "{tabla}" ENABLE ROW LEVEL SECURITY')
    op.drop_constraint("ck_notificacion_estado", "notificaciones_logs")
    op.create_check_constraint(
        "ck_notificacion_estado", "notificaciones_logs",
        "estado IN ('EN_COLA','ENVIADO','ENTREGADO','REINTENTANDO','FALLIDO_PERMANENTE','OMITIDO')",
    )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM comunicados)
        OR EXISTS (SELECT 1 FROM politicas_notificaciones)
        OR EXISTS (SELECT 1 FROM contactos_bloqueados)
        OR EXISTS (SELECT 1 FROM eventos_solvencia_outbox)
        OR EXISTS (SELECT 1 FROM notificaciones_logs
                   WHERE estado = 'OMITIDO' OR recordatorio_vencimiento IS NOT NULL) THEN
        RAISE EXCEPTION 'Hay operaciones de correo; no se permite perder historial';
        END IF; END $$""")
    op.drop_constraint("ck_notificacion_estado", "notificaciones_logs")
    op.drop_column("notificaciones_logs", "recordatorio_dias")
    op.drop_column("notificaciones_logs", "recordatorio_vencimiento")
    op.create_check_constraint(
        "ck_notificacion_estado", "notificaciones_logs",
        "estado IN ('EN_COLA','ENVIADO','ENTREGADO','REINTENTANDO','FALLIDO_PERMANENTE')",
    )
    for tabla in (
        "estado_job_notificaciones", "eventos_solvencia_outbox",
        "contactos_bloqueados", "politicas_notificaciones", "comunicados",
    ):
        op.drop_table(tabla)
