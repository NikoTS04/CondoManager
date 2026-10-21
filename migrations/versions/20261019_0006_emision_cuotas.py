"""Crear/adoptar cuotas y añadir lotes, outbox y la FK pendiente de CON-13.

El backup de Supabase ya contiene cuotas. Se valida y conserva esa tabla;
el downgrade solo la elimina cuando fue creada por esta revisión.
"""

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261019_0006"
down_revision = "20261018_0005"
branch_labels = None
depends_on = None
MARCA = "Creado por CON-11 / Alembic 20261019_0006"


def _normalizar_check(expresion):
    return re.sub(r"[\s()]", "", expresion)


def _validar_cuotas_existentes():
    conexion = op.get_bind()
    inspector = sa.inspect(conexion)
    tabla = "cuotas_mantenimiento"
    columnas = {
        "id": "UUID",
        "departamento_id": "UUID",
        "periodo": "VARCHAR(7)",
        **{
            nombre: "NUMERIC(12, 2)"
            for nombre in (
                "monto_ordinario",
                "monto_extraordinario",
                "monto_mora",
                "monto_descuento",
                "monto_total_exigible",
                "monto_pagado",
            )
        },
        "fecha_emision": "DATE",
        "fecha_vencimiento": "DATE",
        "estado": "VARCHAR(20)",
    }
    reales = {c["name"]: c for c in inspector.get_columns(tabla)}
    for campo, tipo in columnas.items():
        actual = reales.get(campo)
        if actual is None or str(actual["type"]).upper() != tipo or actual["nullable"]:
            raise RuntimeError(
                f"CON-11: esquema incompatible en {tabla}.{campo}; revisar baseline."
            )
    if inspector.get_pk_constraint(tabla)["constrained_columns"] != ["id"]:
        raise RuntimeError(f"CON-11: falta PK UUID en {tabla}.")
    if not any(
        c["column_names"] == ["departamento_id", "periodo"]
        for c in inspector.get_unique_constraints(tabla)
    ):
        raise RuntimeError(f"CON-11: falta unicidad departamento-periodo en {tabla}.")
    esquema = conexion.scalar(sa.text("SELECT current_schema()"))
    if not any(
        fk["constrained_columns"] == ["departamento_id"]
        and fk["referred_table"] == "departamentos"
        and fk["referred_columns"] == ["id"]
        and fk.get("referred_schema") in (None, esquema)
        and fk.get("options", {}).get("ondelete") == "RESTRICT"
        for fk in inspector.get_foreign_keys(tabla)
    ):
        raise RuntimeError(f"CON-11: relación incompatible en {tabla}.departamento_id.")
    # PostgreSQL refleja BETWEEN como AND e IN como ANY con casts explícitos.
    esperados = {
        **{
            f"ck_cuota_{nombre}": f"{nombre} >= 0.00"
            for nombre in (
                "monto_ordinario",
                "monto_extraordinario",
                "monto_mora",
                "monto_descuento",
                "monto_total_exigible",
            )
        },
        "ck_cuota_monto_pagado": ("monto_pagado >= 0.00 AND monto_pagado <= monto_total_exigible"),
        "ck_cuota_estado": (
            "estado::text = ANY (ARRAY['EMITIDA'::character varying, "
            "'PENDIENTE'::character varying, 'PAGO_PARCIAL'::character varying, "
            "'PAGADA'::character varying, 'VENCIDA'::character varying, "
            "'EN_MORA'::character varying]::text[])"
        ),
    }
    checks = {
        c["name"]: _normalizar_check(c["sqltext"]) for c in inspector.get_check_constraints(tabla)
    }
    for nombre, expresion in esperados.items():
        if checks.get(nombre) != _normalizar_check(expresion):
            raise RuntimeError(f"CON-11: check incompatible {tabla}.{nombre}.")
    if conexion.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_constraint "
            "WHERE conrelid = 'cuotas_mantenimiento'::regclass AND NOT convalidated)"
        )
    ):
        raise RuntimeError(f"CON-11: restricciones sin validar en {tabla}.")


def _crear_cuotas():
    op.create_table(
        "cuotas_mantenimiento",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "departamento_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("periodo", sa.String(7), nullable=False),
        *[
            sa.Column(nombre, sa.Numeric(12, 2), nullable=False)
            for nombre in (
                "monto_ordinario",
                "monto_extraordinario",
                "monto_mora",
                "monto_descuento",
                "monto_total_exigible",
                "monto_pagado",
            )
        ],
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.UniqueConstraint("departamento_id", "periodo", name="uq_departamento_periodo"),
        *[
            sa.CheckConstraint(f"{nombre} >= 0.00", name=f"ck_cuota_{nombre}")
            for nombre in (
                "monto_ordinario",
                "monto_extraordinario",
                "monto_mora",
                "monto_descuento",
                "monto_total_exigible",
            )
        ],
        sa.CheckConstraint(
            "monto_pagado BETWEEN 0.00 AND monto_total_exigible", name="ck_cuota_monto_pagado"
        ),
        sa.CheckConstraint(
            "estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA')",
            name="ck_cuota_estado",
        ),
        comment=MARCA,
    )


def upgrade():
    if sa.inspect(op.get_bind()).has_table("cuotas_mantenimiento"):
        _validar_cuotas_existentes()
    else:
        _crear_cuotas()
    op.create_foreign_key(
        "fk_aplicacion_saldo_cuota",
        "aplicaciones_saldo_favor",
        "cuotas_mantenimiento",
        ["cuota_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "lotes_cuotas",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "condominio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("condominios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "presupuesto_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("presupuestos_mensuales.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("periodo", sa.String(7), nullable=False),
        sa.Column("metodo", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(150), nullable=False),
        sa.Column("total_cuotas_emitidas", sa.Integer(), nullable=False),
        sa.Column("monto_total_facturado", sa.Numeric(12, 2), nullable=False),
        sa.Column("cuotas_cubiertas_saldo_favor", sa.Integer(), nullable=False),
        sa.Column("fecha_emision", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.UniqueConstraint("condominio_id", "periodo", name="uq_lote_condominio_periodo"),
        sa.CheckConstraint("monto_total_facturado > 0", name="ck_lote_monto"),
        sa.CheckConstraint("total_cuotas_emitidas > 0", name="ck_lote_cantidad"),
        sa.CheckConstraint("metodo IN ('POR_ALICUOTA', 'EQUITATIVA')", name="ck_lote_metodo"),
    )
    op.create_table(
        "eventos_lote_outbox",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lote_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("lotes_cuotas.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("eventos_lote_outbox")
    op.drop_table("lotes_cuotas")
    op.drop_constraint("fk_aplicacion_saldo_cuota", "aplicaciones_saldo_favor", type_="foreignkey")
    if sa.inspect(op.get_bind()).get_table_comment("cuotas_mantenimiento").get("text") == MARCA:
        op.drop_table("cuotas_mantenimiento")
