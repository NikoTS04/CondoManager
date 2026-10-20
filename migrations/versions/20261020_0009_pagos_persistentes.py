"""CON-70: adoptar pagos sin perder datos y añadir evidencia/revisión/outbox.

No modifica revisiones previas. Las tablas adoptadas sobreviven al downgrade.
Una estructura incompatible detiene la adopción, en vez de reconstruirla.
"""

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261020_0009"
down_revision = "20261020_0008"
branch_labels = None
depends_on = None
MARCA = "Creado por CON-70 / Alembic 20261020_0009"


def _validar(tabla, columnas, relaciones, unicos):
    inspector = sa.inspect(op.get_bind())
    existentes = {c["name"]: c for c in inspector.get_columns(tabla)}
    for nombre, (tipo, nullable) in columnas.items():
        c = existentes.get(nombre)
        if c is None or str(c["type"]).upper() != tipo or c["nullable"] != nullable:
            raise RuntimeError(f"CON-70: esquema incompatible en {tabla}.{nombre}.")
        if tipo == "TIMESTAMP" and not c["type"].timezone:
            raise RuntimeError(f"CON-70: {tabla}.{nombre} debe conservar zona horaria.")
    if inspector.get_pk_constraint(tabla)["constrained_columns"] != ["id"]:
        raise RuntimeError(f"CON-70: falta PK UUID en {tabla}.")
    esquema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    for campo, destino in relaciones.items():
        if not any(
            f["constrained_columns"] == [campo]
            and f["referred_table"] == destino
            and f["referred_columns"] == ["id"]
            and f.get("referred_schema") in (None, esquema)
            and f.get("options", {}).get("ondelete") == "RESTRICT"
            for f in inspector.get_foreign_keys(tabla)
        ):
            raise RuntimeError(f"CON-70: FK incompatible en {tabla}.{campo}.")
    indices = inspector.get_unique_constraints(tabla) + [
        i for i in inspector.get_indexes(tabla) if i.get("unique")
    ]
    for campo in unicos:
        if not any(i["column_names"] == [campo] for i in indices):
            raise RuntimeError(f"CON-70: falta unicidad de {tabla}.{campo}.")
    checks = inspector.get_check_constraints(tabla)
    monto = "monto" if tabla == "comprobantes_pago" else "monto_aplicado"
    if not any(
        re.fullmatch(
            rf"{monto}>0(?:\.0+)?",
            re.sub(r"[\s()]|::numeric", "", c["sqltext"].lower()),
        )
        for c in checks
    ):
        raise RuntimeError(f"CON-70: falta check positivo de {tabla}.{monto}.")
    if tabla == "comprobantes_pago" and not any(
        "estado" in c["sqltext"]
        and set(re.findall(r"'([^']+)'", c["sqltext"]))
        == {"EN_REVISION", "APROBADO", "OBSERVADO", "RECHAZADO"}
        for c in checks
    ):
        raise RuntimeError("CON-70: estados incompatibles en comprobantes_pago.")
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_constraint "
            "WHERE conrelid = to_regclass(:tabla) AND NOT convalidated)"
        ),
        {"tabla": tabla},
    ):
        raise RuntimeError(f"CON-70: restricciones sin validar en {tabla}.")


def upgrade():
    if sa.inspect(op.get_bind()).has_table("comprobantes_pago"):
        _validar(
            "comprobantes_pago",
            {
                "id": ("UUID", False),
                "departamento_id": ("UUID", False),
                "banco_origen": ("VARCHAR(30)", False),
                "numero_operacion": ("VARCHAR(50)", False),
                "fecha_operacion": ("DATE", False),
                "monto": ("NUMERIC(12, 2)", False),
                "url_voucher": ("TEXT", False),
                "idempotency_hash": ("VARCHAR(64)", False),
                "estado": ("VARCHAR(20)", False),
                "motivo_rechazo": ("TEXT", True),
                "conciliado_por": ("UUID", True),
                "conciliado_en": ("TIMESTAMP", True),
                "creado_en": ("TIMESTAMP", False),
            },
            {"departamento_id": "departamentos"},
            ["idempotency_hash"],
        )
    else:
        op.create_table(
            "comprobantes_pago",
            sa.Column("id", pg.UUID(), primary_key=True),
            sa.Column(
                "departamento_id",
                pg.UUID(),
                sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("banco_origen", sa.String(30), nullable=False),
            sa.Column("numero_operacion", sa.String(50), nullable=False),
            sa.Column("fecha_operacion", sa.Date(), nullable=False),
            sa.Column("monto", sa.Numeric(12, 2), nullable=False),
            sa.Column("url_voucher", sa.Text(), nullable=False),
            sa.Column("idempotency_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("estado", sa.String(20), nullable=False, server_default="EN_REVISION"),
            sa.Column("motivo_rechazo", sa.Text(), nullable=True),
            sa.Column("conciliado_por", pg.UUID(), nullable=True),
            sa.Column("conciliado_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("monto > 0.00", name="ck_comprobante_monto"),
            sa.CheckConstraint(
                "estado IN ('EN_REVISION', 'APROBADO', 'RECHAZADO', 'OBSERVADO')",
                name="ck_comprobante_estado",
            ),
            comment=MARCA,
        )
    if sa.inspect(op.get_bind()).has_table("imputaciones_pago"):
        _validar(
            "imputaciones_pago",
            {
                "id": ("UUID", False),
                "comprobante_id": ("UUID", False),
                "cuota_id": ("UUID", False),
                "monto_aplicado": ("NUMERIC(12, 2)", False),
                "fecha_imputacion": ("TIMESTAMP", False),
            },
            {"comprobante_id": "comprobantes_pago", "cuota_id": "cuotas_mantenimiento"},
            [],
        )
    else:
        op.create_table(
            "imputaciones_pago",
            sa.Column("id", pg.UUID(), primary_key=True),
            sa.Column(
                "comprobante_id",
                pg.UUID(),
                sa.ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "cuota_id",
                pg.UUID(),
                sa.ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("monto_aplicado", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "fecha_imputacion",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("monto_aplicado > 0.00", name="ck_imputacion_monto"),
            comment=MARCA,
        )
    op.create_table(
        "archivos_voucher",
        sa.Column("nombre", sa.Text(), primary_key=True),
        sa.Column(
            "departamento_id",
            pg.UUID(),
            sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("usuario_id", pg.UUID(), nullable=False),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "comprobante_id",
            pg.UUID(),
            sa.ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 5242880", name="ck_voucher_size"),
        sa.CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'application/pdf')",
            name="ck_voucher_content_type",
        ),
    )
    op.create_index("idx_voucher_pendientes", "archivos_voucher", ["comprobante_id", "creado_en"])
    op.create_table(
        "revisiones_pago",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column(
            "comprobante_id",
            pg.UUID(),
            sa.ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("actor_id", pg.UUID(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resultado", pg.JSONB(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('APROBADO', 'OBSERVADO', 'RECHAZADO')", name="ck_revision_decision"
        ),
    )
    op.create_index(
        "idx_revision_comprobante_fecha", "revisiones_pago", ["comprobante_id", "creado_en"]
    )
    op.create_table(
        "eventos_pago_outbox",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column(
            "comprobante_id",
            pg.UUID(),
            sa.ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_evento_pago_pendiente", "eventos_pago_outbox", ["publicado_en", "creado_en"]
    )


def downgrade():
    op.drop_table("eventos_pago_outbox")
    op.drop_table("revisiones_pago")
    op.drop_table("archivos_voucher")
    for tabla in ("imputaciones_pago", "comprobantes_pago"):
        if sa.inspect(op.get_bind()).get_table_comment(tabla).get("text") == MARCA:
            op.drop_table(tabla)
