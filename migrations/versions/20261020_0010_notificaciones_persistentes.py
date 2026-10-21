"""Persistir notificaciones, intentos, consumo idempotente y alertas (CON-32/34/36/37)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20261020_0010"
down_revision = "20261020_0009"
branch_labels = None
depends_on = None
MARCA = "Creado por CON-32/37 / Alembic 20261020_0010"


def _id():
    return sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _ts(nombre, nullable=True, ahora=False):
    return sa.Column(
        nombre,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if ahora else None,
    )


def upgrade():
    op.create_table(
        "notificaciones",
        _id(),
        sa.Column(
            "condominio_id",
            UUID(),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "departamento_id", UUID(), sa.ForeignKey("departamentos.id", ondelete="RESTRICT")
        ),
        sa.Column("usuario_id", UUID(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT")),
        sa.Column("evento_id", UUID(), nullable=False),
        sa.Column("tipo_evento", sa.String(60), nullable=False),
        sa.Column("plantilla", sa.String(50), nullable=False),
        sa.Column("origen_tipo", sa.String(20), nullable=False),
        sa.Column("origen_id", UUID(), nullable=False),
        sa.Column("clave_deduplicacion", sa.String(255), nullable=False),
        sa.Column("canal", sa.String(10), nullable=False, server_default="EMAIL"),
        sa.Column("destinatario", sa.String(150), nullable=False),
        sa.Column("asunto", sa.String(200)),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("contexto", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("estado", sa.String(20), nullable=False, server_default="EN_COLA"),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ciclo", sa.Integer(), nullable=False, server_default="1"),
        _ts("proximo_intento_en"),
        _ts("bloqueado_hasta"),
        sa.Column("bloqueado_por", sa.String(80)),
        sa.Column("transporte", sa.String(40)),
        sa.Column("transporte_simulado", sa.Boolean()),
        sa.Column("proveedor_message_id", sa.String(150)),
        sa.Column("error_codigo", sa.String(40)),
        sa.Column("error_mensaje", sa.Text()),
        _ts("creado_en", nullable=False, ahora=True),
        _ts("actualizado_en", nullable=False, ahora=True),
        _ts("aceptado_en"),
        _ts("entregado_en"),
        sa.UniqueConstraint("clave_deduplicacion", name="uq_notificacion_entrega_logica"),
        sa.CheckConstraint(
            "estado IN ('EN_COLA', 'REINTENTANDO', 'ACEPTADO', 'ENTREGADO', 'FALLIDO_PERMANENTE')",
            name="ck_notificacion_estado",
        ),
        sa.CheckConstraint(
            "canal IN ('EMAIL', 'WHATSAPP', 'SMS', 'PUSH')", name="ck_notificacion_canal"
        ),
        sa.CheckConstraint(
            "origen_tipo IN ('CUOTA', 'COMPROBANTE', 'RESERVA', 'COMUNICADO', 'USUARIO')",
            name="ck_notificacion_origen",
        ),
        sa.CheckConstraint("intentos BETWEEN 0 AND 4", name="ck_notificacion_intentos"),
        sa.CheckConstraint("ciclo >= 1", name="ck_notificacion_ciclo"),
        comment=MARCA,
    )
    op.create_index(
        "idx_notificaciones_pendientes",
        "notificaciones",
        ["proximo_intento_en"],
        postgresql_where=sa.text("estado IN ('EN_COLA', 'REINTENTANDO')"),
    )
    op.create_index(
        "idx_notificaciones_condominio", "notificaciones", ["condominio_id", "creado_en"]
    )
    op.create_index(
        "idx_notificaciones_departamento", "notificaciones", ["departamento_id", "creado_en"]
    )
    op.create_index("idx_notificaciones_origen", "notificaciones", ["origen_tipo", "origen_id"])

    op.create_table(
        "notificacion_intentos",
        _id(),
        sa.Column(
            "notificacion_id",
            UUID(),
            sa.ForeignKey("notificaciones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ciclo", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(80), nullable=False),
        sa.Column("transporte", sa.String(40), nullable=False),
        sa.Column("transporte_simulado", sa.Boolean(), nullable=False),
        sa.Column("resultado", sa.String(20), nullable=False),
        sa.Column("codigo", sa.String(40)),
        sa.Column("detalle", sa.Text()),
        sa.Column("proveedor_message_id", sa.String(150)),
        _ts("iniciado_en", nullable=False),
        _ts("finalizado_en", nullable=False),
        sa.UniqueConstraint("notificacion_id", "ciclo", "numero", name="uq_intento_numero"),
        sa.CheckConstraint("numero BETWEEN 1 AND 4", name="ck_intento_numero"),
        sa.CheckConstraint(
            "resultado IN ('ACEPTADO', 'FALLO_TEMPORAL', 'FALLO_DEFINITIVO')",
            name="ck_intento_resultado",
        ),
        comment=MARCA,
    )

    op.create_table(
        "eventos_consumidos",
        sa.Column("consumidor", sa.String(60), nullable=False),
        sa.Column("event_id", UUID(), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("notificaciones_creadas", sa.Integer(), nullable=False, server_default="0"),
        _ts("procesado_en", nullable=False, ahora=True),
        sa.PrimaryKeyConstraint("consumidor", "event_id", name="pk_eventos_consumidos"),
        comment=MARCA,
    )

    op.create_table(
        "alertas_administrativas",
        _id(),
        sa.Column(
            "condominio_id",
            UUID(),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "notificacion_id",
            UUID(),
            sa.ForeignKey("notificaciones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(40), nullable=False, server_default="NOTIFICACION_FALLIDA"),
        sa.Column("severidad", sa.String(10), nullable=False, server_default="BAJA"),
        sa.Column("mensaje", sa.Text(), nullable=False),
        _ts("creado_en", nullable=False, ahora=True),
        _ts("atendida_en"),
        sa.Column("atendida_por", UUID()),
        sa.UniqueConstraint("notificacion_id", "tipo", name="uq_alerta_notificacion_tipo"),
        sa.CheckConstraint("severidad IN ('BAJA', 'MEDIA', 'ALTA')", name="ck_alerta_severidad"),
        comment=MARCA,
    )
    op.create_index(
        "idx_alertas_abiertas",
        "alertas_administrativas",
        ["condominio_id", "creado_en"],
        postgresql_where=sa.text("atendida_en IS NULL"),
    )


def downgrade():
    op.drop_index("idx_alertas_abiertas", table_name="alertas_administrativas")
    op.drop_table("alertas_administrativas")
    op.drop_table("eventos_consumidos")
    op.drop_table("notificacion_intentos")
    for indice in (
        "idx_notificaciones_origen",
        "idx_notificaciones_departamento",
        "idx_notificaciones_condominio",
        "idx_notificaciones_pendientes",
    ):
        op.drop_index(indice, table_name="notificaciones")
    op.drop_table("notificaciones")
