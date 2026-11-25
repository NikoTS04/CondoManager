"""CON-84: alertas de fallos definitivos con origen (correo o job) y correlación."""

import sqlalchemy as sa
from alembic import op

revision = "20261125_0025"
down_revision = "20261124_0024"
branch_labels = None
depends_on = None

TIPOS_ANTERIORES = (
    "ERROR_DEFINITIVO",
    "INTENTOS_AGOTADOS",
    "ACEPTACION_INCIERTA",
    "DESTINATARIO_INVALIDO",
    "PROVEEDOR_NO_CONFIGURADO",
)
TIPOS = (*TIPOS_ANTERIORES, "JOB_FALLO_DEFINITIVO")


def _lista(tipos):
    return "tipo IN ('" + "','".join(tipos) + "')"


def upgrade():
    op.add_column(
        "notificaciones_alertas",
        sa.Column("origen_tipo", sa.String(10), nullable=False, server_default="CORREO"),
    )
    op.add_column("notificaciones_alertas", sa.Column("origen_id", sa.String(100)))
    op.add_column("notificaciones_alertas", sa.Column("referencia_correlacion", sa.String(64)))
    op.execute("UPDATE notificaciones_alertas SET origen_id = notificacion_id::text")
    op.alter_column("notificaciones_alertas", "origen_id", nullable=False)
    op.alter_column("notificaciones_alertas", "origen_tipo", server_default=None)
    op.alter_column("notificaciones_alertas", "notificacion_id", nullable=True)
    op.alter_column("notificaciones_alertas", "condominio_id", nullable=True)
    op.drop_constraint("uq_alerta_notificacion_tipo", "notificaciones_alertas", type_="unique")
    op.create_unique_constraint(
        "uq_alerta_origen_tipo",
        "notificaciones_alertas",
        ["origen_tipo", "origen_id", "ciclo", "tipo"],
    )
    op.drop_constraint("ck_alerta_tipo", "notificaciones_alertas", type_="check")
    op.create_check_constraint("ck_alerta_tipo", "notificaciones_alertas", _lista(TIPOS))
    op.create_check_constraint(
        "ck_alerta_origen_tipo", "notificaciones_alertas", "origen_tipo IN ('CORREO','JOB')"
    )
    op.create_check_constraint(
        "ck_alerta_origen",
        "notificaciones_alertas",
        "origen_tipo <> 'CORREO' OR (notificacion_id IS NOT NULL AND condominio_id IS NOT NULL)",
    )


def downgrade():
    # Las alertas de job no tienen notificación ni condominio y no caben en el esquema anterior.
    op.execute("DELETE FROM notificaciones_alertas WHERE origen_tipo = 'JOB'")
    op.drop_constraint("ck_alerta_origen", "notificaciones_alertas", type_="check")
    op.drop_constraint("ck_alerta_origen_tipo", "notificaciones_alertas", type_="check")
    op.drop_constraint("ck_alerta_tipo", "notificaciones_alertas", type_="check")
    op.create_check_constraint("ck_alerta_tipo", "notificaciones_alertas", _lista(TIPOS_ANTERIORES))
    op.drop_constraint("uq_alerta_origen_tipo", "notificaciones_alertas", type_="unique")
    op.create_unique_constraint(
        "uq_alerta_notificacion_tipo",
        "notificaciones_alertas",
        ["notificacion_id", "ciclo", "tipo"],
    )
    op.alter_column("notificaciones_alertas", "condominio_id", nullable=False)
    op.alter_column("notificaciones_alertas", "notificacion_id", nullable=False)
    op.drop_column("notificaciones_alertas", "referencia_correlacion")
    op.drop_column("notificaciones_alertas", "origen_id")
    op.drop_column("notificaciones_alertas", "origen_tipo")
