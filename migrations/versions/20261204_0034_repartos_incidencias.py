"""Reparto por costo y destinos de pago independientes de cuotas."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261204_0034"
down_revision = "20261203_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "comprobantes_pago",
        sa.Column(
            "cargos_incidencia_ids",
            JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_table(
        "repartos_incidencia",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("condominio_id", sa.Uuid(), sa.ForeignKey("condominios.id"), nullable=False),
        sa.Column("incidencia_id", sa.Uuid(), sa.ForeignKey("incidencias.id"), nullable=False),
        sa.Column(
            "actualizacion_id",
            sa.Uuid(),
            sa.ForeignKey("incidencias_actualizaciones.id"),
            nullable=False,
        ),
        sa.Column("clave_idempotencia", sa.Uuid(), nullable=False),
        sa.Column("hash_solicitud", sa.String(64), nullable=False),
        sa.Column("concepto", sa.String(200), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("alcance", sa.String(20), nullable=False),
        sa.Column("metodo", sa.String(20), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("instantanea", JSONB(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("actualizacion_id", name="uq_reparto_costo"),
        sa.UniqueConstraint("condominio_id", "clave_idempotencia", name="uq_reparto_clave"),
        sa.CheckConstraint("monto > 0", name="ck_reparto_monto"),
        sa.CheckConstraint("metodo IN ('EQUITATIVA','POR_ALICUOTA')", name="ck_reparto_metodo"),
        sa.CheckConstraint("alcance IN ('TODOS','SELECCIONADOS')", name="ck_reparto_alcance"),
    )
    op.create_index(
        "ix_repartos_incidencia_condominio_id", "repartos_incidencia", ["condominio_id"]
    )
    op.create_table(
        "cargos_incidencia",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reparto_id", sa.Uuid(), sa.ForeignKey("repartos_incidencia.id"), nullable=False),
        sa.Column("departamento_id", sa.Uuid(), sa.ForeignKey("departamentos.id"), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("pagado", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("reparto_id", "departamento_id", name="uq_cargo_reparto_unidad"),
        sa.CheckConstraint("monto >= 0 AND pagado BETWEEN 0 AND monto", name="ck_cargo_importes"),
    )
    op.create_index(
        "ix_cargos_incidencia_departamento_id", "cargos_incidencia", ["departamento_id"]
    )
    op.create_table(
        "destinos_pago_incidencia",
        sa.Column(
            "comprobante_id", sa.Uuid(), sa.ForeignKey("comprobantes_pago.id"), primary_key=True
        ),
        sa.Column("cargo_id", sa.Uuid(), sa.ForeignKey("cargos_incidencia.id"), primary_key=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("monto > 0", name="ck_destino_incidencia_monto"),
    )
    # Solo backend: ni anon ni authenticated acceden directamente por PostgREST.
    for tabla in ("repartos_incidencia", "cargos_incidencia", "destinos_pago_incidencia"):
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table("destinos_pago_incidencia")
    op.drop_table("cargos_incidencia")
    op.drop_table("repartos_incidencia")
    op.drop_column("comprobantes_pago", "cargos_incidencia_ids")
