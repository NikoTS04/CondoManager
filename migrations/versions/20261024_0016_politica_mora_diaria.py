"""Configuración diaria aditiva; no modifica políticas ni cuotas existentes."""

import sqlalchemy as sa
from alembic import op

revision = "20261024_0016"
down_revision = "20261021_0015"
branch_labels = None
depends_on = None

LEGACY = (
    "(regla_mora_tipo = 'MONTO_FIJO' AND monto_mora_fijo IS NOT NULL "
    "AND tasa_mora_porcentaje IS NULL) OR "
    "(regla_mora_tipo = 'PORCENTAJE_SALDO' AND tasa_mora_porcentaje IS NOT NULL "
    "AND monto_mora_fijo IS NULL)"
)


def upgrade():
    op.add_column("cuotas_mantenimiento", sa.Column("dias_gracia_aplicados", sa.SmallInteger()))
    # Congela la gracia efectiva de adopción, sin fingir conocer la política original.
    op.execute(
        "UPDATE cuotas_mantenimiento q SET dias_gracia_aplicados = c.dias_gracia FROM departamentos d JOIN edificios e ON e.id = d.edificio_id JOIN condominios c ON c.id = e.condominio_id WHERE q.departamento_id = d.id"
    )
    op.create_check_constraint(
        "ck_cuota_gracia_aplicada", "cuotas_mantenimiento", "dias_gracia_aplicados BETWEEN 0 AND 30"
    )
    op.add_column("condominios", sa.Column("monto_mora_diario", sa.Numeric(12, 2)))
    op.add_column(
        "condominios",
        sa.Column("politica_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_constraint("ck_condominio_regla_mora", "condominios", type_="check")
    op.drop_constraint("ck_condominio_configuracion_mora", "condominios", type_="check")
    op.create_check_constraint(
        "ck_condominio_regla_mora",
        "condominios",
        "regla_mora_tipo IN ('MONTO_DIARIO', 'MONTO_FIJO', 'PORCENTAJE_SALDO')",
    )
    op.create_check_constraint(
        "ck_condominio_configuracion_mora",
        "condominios",
        f"(({LEGACY}) AND monto_mora_diario IS NULL) OR (regla_mora_tipo = 'MONTO_DIARIO' AND monto_mora_diario IS NOT NULL AND monto_mora_diario > 0 AND monto_mora_fijo IS NULL AND tasa_mora_porcentaje IS NULL)",
    )
    op.create_check_constraint(
        "ck_condominio_politica_version", "condominios", "politica_version > 0"
    )


def downgrade():
    # No convertir ni borrar políticas diarias para forzar compatibilidad.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM condominios WHERE regla_mora_tipo = 'MONTO_DIARIO') THEN RAISE EXCEPTION 'Existen políticas diarias; concilie antes del downgrade'; END IF; END $$"
    )
    op.drop_constraint("ck_condominio_politica_version", "condominios", type_="check")
    op.drop_constraint("ck_condominio_configuracion_mora", "condominios", type_="check")
    op.drop_constraint("ck_condominio_regla_mora", "condominios", type_="check")
    op.create_check_constraint(
        "ck_condominio_regla_mora",
        "condominios",
        "regla_mora_tipo IN ('MONTO_FIJO', 'PORCENTAJE_SALDO')",
    )
    op.create_check_constraint("ck_condominio_configuracion_mora", "condominios", LEGACY)
    op.drop_column("condominios", "politica_version")
    op.drop_column("condominios", "monto_mora_diario")
    op.drop_constraint("ck_cuota_gracia_aplicada", "cuotas_mantenimiento", type_="check")
    op.drop_column("cuotas_mantenimiento", "dias_gracia_aplicados")
