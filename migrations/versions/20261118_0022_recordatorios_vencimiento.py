"""CON-33: estado SUPRIMIDO para recordatorios cuya cuota dejó de ser elegible al despachar."""

from alembic import op

revision = "20261118_0022"
down_revision = "20261113_0021"
branch_labels = None
depends_on = None

ESTADOS = "'EN_COLA','ENVIADO','ENTREGADO','REINTENTANDO','FALLIDO_PERMANENTE'"


def upgrade():
    op.drop_constraint("ck_notificacion_estado", "notificaciones_logs", type_="check")
    op.create_check_constraint(
        "ck_notificacion_estado", "notificaciones_logs", f"estado IN ({ESTADOS},'SUPRIMIDO')"
    )


def downgrade():
    # El esquema anterior no conoce la supresión: se conserva como terminal sin reenvío.
    op.execute(
        "UPDATE notificaciones_logs SET estado = 'FALLIDO_PERMANENTE' WHERE estado = 'SUPRIMIDO'"
    )
    op.drop_constraint("ck_notificacion_estado", "notificaciones_logs", type_="check")
    op.create_check_constraint(
        "ck_notificacion_estado", "notificaciones_logs", f"estado IN ({ESTADOS})"
    )
