"""Asignación de incidencias y destinatarios externos en la cola (CON-55).

`responsable_proveedor_id` y `destinatario_externo_id` no tienen llave foránea
hasta que CON-48 entregue el directorio de proveedores.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261127_0027"
down_revision = "20261126_0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incidencias", sa.Column("asignacion_actual_id", sa.Uuid(), nullable=True))
    op.add_column(
        "incidencias",
        sa.Column(
            "responsable_usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("incidencias", sa.Column("responsable_proveedor_id", sa.Uuid(), nullable=True))
    for nombre in ("proveedor_nombre", "correo_proveedor"):
        op.add_column("incidencias", sa.Column(nombre, sa.Text(), nullable=True))
    for nombre in ("fecha_asignacion", "plazo"):
        op.add_column("incidencias", sa.Column(nombre, sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_incidencia_estado",
        "incidencias",
        "estado IN ('REGISTRADO','RECHAZADO','ASIGNADO','EN_PROCESO','RESUELTO','CERRADO')",
    )
    op.create_check_constraint(
        "ck_incidencia_responsable",
        "incidencias",
        "NOT (responsable_usuario_id IS NOT NULL AND responsable_proveedor_id IS NOT NULL)",
    )

    op.create_table(
        "incidencias_asignaciones",
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
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("clave_idempotencia", sa.Uuid(), nullable=False),
        sa.Column("hash_solicitud", sa.Text(), nullable=False),
        sa.Column(
            "responsable_usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("responsable_proveedor_id", sa.Uuid(), nullable=True),
        sa.Column("proveedor_nombre", sa.Text(), nullable=True),
        sa.Column("correo_proveedor", sa.Text(), nullable=True),
        sa.Column("plazo", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "condominio_id",
            "incidencia_id",
            "clave_idempotencia",
            name="uq_asignacion_operacion",
        ),
        sa.CheckConstraint(
            "NOT (responsable_usuario_id IS NOT NULL AND responsable_proveedor_id IS NOT NULL)",
            name="ck_asignacion_responsable",
        ),
    )
    op.create_index(
        "ix_incidencias_asignaciones_incidencia_id",
        "incidencias_asignaciones",
        ["incidencia_id"],
    )

    op.drop_constraint("uq_notificacion_logica", "notificaciones_logs", type_="unique")
    op.alter_column("notificaciones_logs", "usuario_destinatario_id", nullable=True)
    op.add_column(
        "notificaciones_logs", sa.Column("destinatario_externo_id", sa.Uuid(), nullable=True)
    )
    op.create_unique_constraint(
        "uq_notificacion_logica",
        "notificaciones_logs",
        ["evento_id", "operacion_id", "usuario_destinatario_id", "canal"],
    )
    op.create_unique_constraint(
        "uq_notificacion_logica_externa",
        "notificaciones_logs",
        ["evento_id", "operacion_id", "destinatario_externo_id", "canal"],
    )
    op.create_check_constraint(
        "ck_notificacion_destinatario",
        "notificaciones_logs",
        "(usuario_destinatario_id IS NOT NULL) <> (destinatario_externo_id IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("ck_notificacion_destinatario", "notificaciones_logs", type_="check")
    op.drop_constraint("uq_notificacion_logica_externa", "notificaciones_logs", type_="unique")
    op.drop_column("notificaciones_logs", "destinatario_externo_id")
    op.execute("DELETE FROM notificaciones_logs WHERE usuario_destinatario_id IS NULL")
    op.alter_column("notificaciones_logs", "usuario_destinatario_id", nullable=False)
    op.drop_constraint("uq_notificacion_logica", "notificaciones_logs", type_="unique")
    op.create_unique_constraint(
        "uq_notificacion_logica",
        "notificaciones_logs",
        ["evento_id", "operacion_id", "usuario_destinatario_id", "canal"],
    )

    op.drop_index("ix_incidencias_asignaciones_incidencia_id", "incidencias_asignaciones")
    op.drop_table("incidencias_asignaciones")
    op.drop_constraint("ck_incidencia_responsable", "incidencias", type_="check")
    op.drop_constraint("ck_incidencia_estado", "incidencias", type_="check")
    for nombre in ("plazo", "fecha_asignacion", "correo_proveedor", "proveedor_nombre"):
        op.drop_column("incidencias", nombre)
    op.drop_column("incidencias", "responsable_proveedor_id")
    op.drop_column("incidencias", "responsable_usuario_id")
    op.drop_column("incidencias", "asignacion_actual_id")
