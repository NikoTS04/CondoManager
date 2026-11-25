"""Persistencia inicial CON-51/52: egresos, aprobaciones, pagos y caja.

Las columnas proveedor_id/contrato_id son referencias UUID temporales sin FK
física. CON-48/49 deberá añadirlas en una revisión descendiente después de
integrar las tablas reales. No crear tablas placeholder ni una rama Alembic.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20261127_0027"
down_revision = "20261126_0026"
branch_labels = None
depends_on = None


def _uuid_fk(columna, tabla, *, nullable=False):
    return sa.Column(
        columna,
        pg.UUID(as_uuid=True),
        sa.ForeignKey(f"{tabla}.id", ondelete="RESTRICT"),
        nullable=nullable,
    )


def upgrade():
    op.create_table(
        "egresos",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        _uuid_fk("concepto_id", "conceptos_presupuestales"),
        # FK diferidas: las tablas proveedor/contrato no están en esta cadena.
        sa.Column("proveedor_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("contrato_id", pg.UUID(as_uuid=True), nullable=True),
        _uuid_fk("presupuesto_id", "presupuestos_mensuales", nullable=True),
        sa.Column("item_presupuesto_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("descripcion", sa.String(500), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("fecha_gasto", sa.Date(), nullable=False),
        sa.Column("monto_pactado", sa.Numeric(12, 2), nullable=True),
        sa.Column("monto_solicitado", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_aprobado", sa.Numeric(12, 2), nullable=True),
        sa.Column("monto_pagado", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("estado", sa.String(30), nullable=False, server_default="BORRADOR"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _uuid_fk("creado_por", "usuarios"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", "id", name="uq_egreso_condominio_id"),
        sa.CheckConstraint("moneda IN ('PEN','USD')", name="ck_egreso_moneda"),
        sa.CheckConstraint(
            "monto_solicitado > 0 AND (monto_pactado IS NULL OR monto_pactado > 0)",
            name="ck_egreso_importes_solicitud",
        ),
        sa.CheckConstraint(
            "monto_aprobado IS NULL OR monto_aprobado > 0", name="ck_egreso_monto_aprobado"
        ),
        sa.CheckConstraint(
            "monto_pagado >= 0 AND (monto_aprobado IS NULL OR monto_pagado <= monto_aprobado)",
            name="ck_egreso_monto_pagado",
        ),
        sa.CheckConstraint(
            "(presupuesto_id IS NULL) = (item_presupuesto_id IS NULL)",
            name="ck_egreso_presupuesto_item_par",
        ),
        sa.CheckConstraint(
            "contrato_id IS NULL OR proveedor_id IS NOT NULL",
            name="ck_egreso_contrato_requiere_proveedor",
        ),
        sa.CheckConstraint("version > 0", name="ck_egreso_version"),
        sa.CheckConstraint(
            "estado IN ('BORRADOR','PENDIENTE_APROBACION','APROBADO','RECHAZADO',"
            "'PAGO_PARCIAL','PAGADO','CANCELADO')",
            name="ck_egreso_estado",
        ),
    )
    op.create_index("ix_egreso_contexto_fecha", "egresos", ["condominio_id", "fecha_gasto", "id"])
    op.create_index(
        "ix_egreso_contexto_estado", "egresos", ["condominio_id", "estado", "creado_en"]
    )
    op.create_index("ix_egreso_proveedor", "egresos", ["condominio_id", "proveedor_id"])
    op.create_index("ix_egreso_concepto", "egresos", ["condominio_id", "concepto_id"])

    op.create_table(
        "documentos_financieros",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("egreso_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("archivo_nombre", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(160), nullable=False),
        _uuid_fk("creado_por", "usuarios"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", "id", name="uq_documento_financiero_condominio_id"),
        sa.UniqueConstraint("storage_key", name="uq_documento_financiero_storage_key"),
        sa.ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_documento_egreso_contexto",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "(tipo IN ('SUSTENTO','EVIDENCIA_PAGO') AND egreso_id IS NOT NULL) OR "
            "(tipo = 'APERTURA_CAJA' AND egreso_id IS NULL)",
            name="ck_documento_financiero_contexto",
        ),
        sa.CheckConstraint(
            "position('/' in archivo_nombre) = 0 AND position(chr(92) in archivo_nombre) = 0 "
            "AND archivo_nombre !~ '[[:cntrl:]]' AND archivo_nombre NOT IN ('.','..')",
            name="ck_documento_financiero_nombre_seguro",
        ),
        sa.CheckConstraint("tamano_bytes > 0", name="ck_documento_financiero_tamano"),
        sa.CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="ck_documento_financiero_sha256"),
        sa.CheckConstraint(
            "storage_key ~ '^[A-Za-z0-9._-]{1,160}$' AND storage_key NOT IN ('.','..')",
            name="ck_documento_financiero_storage_key_segura",
        ),
    )
    op.create_index(
        "ix_documento_financiero_contexto",
        "documentos_financieros",
        ["condominio_id", "egreso_id", "creado_en"],
    )

    op.create_table(
        "aprobaciones_egreso",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("egreso_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("version_egreso", sa.Integer(), nullable=False),
        sa.Column("monto_revisado", sa.Numeric(12, 2), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("estado_anterior", sa.String(30), nullable=False),
        sa.Column("estado_nuevo", sa.String(30), nullable=False),
        sa.Column("resultado", sa.String(20), nullable=False),
        _uuid_fk("actor_id", "usuarios"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_aprobacion_egreso_contexto",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "egreso_id", "version_egreso", "actor_id", name="uq_aprobacion_egreso_version_actor"
        ),
        sa.CheckConstraint("version_egreso > 0", name="ck_aprobacion_egreso_version"),
        sa.CheckConstraint("monto_revisado > 0", name="ck_aprobacion_egreso_monto"),
        sa.CheckConstraint(
            "decision IN ('APROBAR','RECHAZAR')", name="ck_aprobacion_egreso_decision"
        ),
        sa.CheckConstraint(
            "resultado IN ('EXITOSO','FALLIDO')", name="ck_aprobacion_egreso_resultado"
        ),
    )
    op.create_index(
        "ix_aprobacion_egreso_historial",
        "aprobaciones_egreso",
        ["condominio_id", "egreso_id", "creado_en"],
    )

    op.create_table(
        "historial_egreso",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("egreso_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("accion", sa.String(40), nullable=False),
        sa.Column("estado_anterior", sa.String(30), nullable=True),
        sa.Column("estado_nuevo", sa.String(30), nullable=False),
        sa.Column("monto_revisado", sa.Numeric(12, 2), nullable=True),
        sa.Column("version_egreso", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("resultado", sa.String(20), nullable=False),
        _uuid_fk("actor_id", "usuarios"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado_anterior_snapshot", pg.JSONB(), nullable=False),
        sa.Column("estado_posterior_snapshot", pg.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_historial_egreso_contexto",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("version_egreso > 0", name="ck_historial_egreso_version"),
        sa.CheckConstraint(
            "monto_revisado IS NULL OR monto_revisado > 0", name="ck_historial_egreso_monto"
        ),
        sa.CheckConstraint(
            "resultado IN ('EXITOSO','FALLIDO')", name="ck_historial_egreso_resultado"
        ),
    )
    op.create_index(
        "ix_historial_egreso_timeline",
        "historial_egreso",
        ["condominio_id", "egreso_id", "creado_en"],
    )

    op.create_table(
        "configuracion_aprobacion_egreso",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("umbral", sa.Numeric(12, 2), nullable=False),
        sa.Column("politica", sa.String(30), nullable=False, server_default="UMBRAL_ESCALONADO"),
        sa.Column("aprobaciones_hasta_umbral", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aprobaciones_sobre_umbral", sa.Integer(), nullable=False, server_default="2"),
        sa.Column(
            "pagos_parciales_habilitados", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _uuid_fk("actualizado_por", "usuarios"),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", name="uq_config_aprobacion_condominio"),
        sa.CheckConstraint("umbral >= 0", name="ck_config_aprobacion_umbral"),
        sa.CheckConstraint("politica = 'UMBRAL_ESCALONADO'", name="ck_config_aprobacion_politica"),
        sa.CheckConstraint(
            "aprobaciones_hasta_umbral = 1 AND aprobaciones_sobre_umbral = 2",
            name="ck_config_aprobacion_conteo_escalonado",
        ),
        sa.CheckConstraint("version > 0", name="ck_config_aprobacion_version"),
    )

    op.create_table(
        "cuentas_caja",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("cuenta_referencia", sa.String(100), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", "id", name="uq_cuenta_caja_condominio_id"),
        sa.UniqueConstraint(
            "condominio_id", "moneda", "cuenta_referencia", name="uq_cuenta_caja_alias_moneda"
        ),
        sa.CheckConstraint("moneda IN ('PEN','USD')", name="ck_cuenta_caja_moneda"),
    )

    op.create_table(
        "aperturas_caja",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("cuenta_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("documento_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("saldo", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha_corte", sa.Date(), nullable=False),
        sa.Column("referencia", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        _uuid_fk("actor_id", "usuarios"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", "id", name="uq_apertura_caja_condominio_id"),
        sa.ForeignKeyConstraint(
            ["condominio_id", "cuenta_id"],
            ["cuentas_caja.condominio_id", "cuentas_caja.id"],
            name="fk_apertura_caja_contexto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["condominio_id", "documento_id"],
            ["documentos_financieros.condominio_id", "documentos_financieros.id"],
            name="fk_apertura_caja_documento_contexto",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("cuenta_id", name="uq_apertura_caja_cuenta"),
        sa.UniqueConstraint("documento_id", name="uq_apertura_caja_documento"),
        sa.UniqueConstraint(
            "condominio_id", "idempotency_key", name="uq_apertura_caja_idempotency"
        ),
        sa.CheckConstraint("saldo >= 0", name="ck_apertura_caja_saldo"),
        sa.CheckConstraint("request_hash ~ '^[a-f0-9]{64}$'", name="ck_apertura_caja_hash"),
    )
    op.create_index(
        "ix_apertura_caja_condominio_fecha", "aperturas_caja", ["condominio_id", "fecha_corte"]
    )

    op.create_table(
        "pagos_egreso",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("condominio_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("egreso_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("cuenta_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("documento_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("fecha_pago", sa.Date(), nullable=False),
        sa.Column("referencia", sa.String(200), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        _uuid_fk("actor_id", "usuarios"),
        sa.Column("idempotency_scope", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("condominio_id", "id", name="uq_pago_egreso_condominio_id"),
        sa.ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_pago_egreso_contexto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["condominio_id", "cuenta_id"],
            ["cuentas_caja.condominio_id", "cuentas_caja.id"],
            name="fk_pago_cuenta_contexto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["condominio_id", "documento_id"],
            ["documentos_financieros.condominio_id", "documentos_financieros.id"],
            name="fk_pago_egreso_documento_contexto",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "condominio_id",
            "idempotency_scope",
            "idempotency_key",
            name="uq_pago_egreso_idempotency",
        ),
        sa.CheckConstraint("monto > 0", name="ck_pago_egreso_monto"),
        sa.CheckConstraint("moneda IN ('PEN','USD')", name="ck_pago_egreso_moneda"),
        sa.CheckConstraint(
            "estado IN ('CONFIRMADO','FALLIDO','REVERSADO')", name="ck_pago_egreso_estado"
        ),
        sa.CheckConstraint(
            "idempotency_scope IN ('CONFIRMAR','FALLIDO')", name="ck_pago_egreso_idem_scope"
        ),
        sa.CheckConstraint(
            "(estado = 'CONFIRMADO' AND idempotency_scope = 'CONFIRMAR' AND documento_id IS NOT NULL) "
            "OR (estado = 'FALLIDO' AND idempotency_scope = 'FALLIDO') "
            "OR (estado = 'REVERSADO' AND idempotency_scope = 'CONFIRMAR' AND documento_id IS NOT NULL)",
            name="ck_pago_egreso_documento_scope",
        ),
        sa.CheckConstraint("request_hash ~ '^[a-f0-9]{64}$'", name="ck_pago_egreso_request_hash"),
    )
    op.create_index(
        "ix_pago_egreso_contexto_fecha",
        "pagos_egreso",
        ["condominio_id", "egreso_id", "fecha_pago"],
    )

    op.create_table(
        "reversos_pago_egreso",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("pago_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        _uuid_fk("actor_id", "usuarios"),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["condominio_id", "pago_id"],
            ["pagos_egreso.condominio_id", "pagos_egreso.id"],
            name="fk_reverso_pago_contexto",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("pago_id", name="uq_reverso_pago_unico"),
        sa.UniqueConstraint("condominio_id", "idempotency_key", name="uq_reverso_pago_idempotency"),
        sa.CheckConstraint("monto > 0", name="ck_reverso_pago_monto"),
        sa.CheckConstraint("request_hash ~ '^[a-f0-9]{64}$'", name="ck_reverso_pago_request_hash"),
    )
    op.create_index(
        "ix_reverso_pago_contexto_fecha", "reversos_pago_egreso", ["condominio_id", "creado_en"]
    )

    op.create_table(
        "movimientos_caja",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("condominio_id", "condominios"),
        sa.Column("cuenta_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("apertura_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("pago_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("reverso_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("importe", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha_operacion", sa.Date(), nullable=False),
        sa.Column("reconocido_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["condominio_id", "cuenta_id"],
            ["cuentas_caja.condominio_id", "cuentas_caja.id"],
            name="fk_movimiento_caja_contexto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["condominio_id", "apertura_id"],
            ["aperturas_caja.condominio_id", "aperturas_caja.id"],
            name="fk_movimiento_caja_apertura_contexto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["condominio_id", "pago_id"],
            ["pagos_egreso.condominio_id", "pagos_egreso.id"],
            name="fk_movimiento_caja_pago_contexto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["condominio_id", "reverso_id"],
            ["reversos_pago_egreso.condominio_id", "reversos_pago_egreso.id"],
            name="fk_movimiento_caja_reverso_contexto",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("apertura_id", name="uq_movimiento_caja_apertura"),
        sa.UniqueConstraint("pago_id", name="uq_movimiento_caja_pago"),
        sa.UniqueConstraint("reverso_id", name="uq_movimiento_caja_reverso"),
        sa.CheckConstraint(
            "(tipo = 'APERTURA' AND apertura_id IS NOT NULL AND pago_id IS NULL "
            "AND reverso_id IS NULL AND importe >= 0) OR "
            "(tipo = 'PAGO_EGRESO' AND apertura_id IS NULL AND pago_id IS NOT NULL "
            "AND reverso_id IS NULL AND importe < 0) OR "
            "(tipo = 'REVERSO_PAGO' AND apertura_id IS NULL AND pago_id IS NULL "
            "AND reverso_id IS NOT NULL AND importe > 0)",
            name="ck_movimiento_caja_origen_importe",
        ),
    )
    op.create_index(
        "ix_movimiento_caja_contexto_fecha",
        "movimientos_caja",
        ["condominio_id", "cuenta_id", "reconocido_en"],
    )

    # El historial, documentos, aperturas, decisiones y ledger son append-only.
    op.execute(
        """CREATE FUNCTION proteger_egreso_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'Registro financiero inmutable; registre una compensacion';
        END; $$ LANGUAGE plpgsql"""
    )
    for table in (
        "documentos_financieros",
        "aprobaciones_egreso",
        "historial_egreso",
        "aperturas_caja",
        "reversos_pago_egreso",
        "movimientos_caja",
    ):
        op.execute(
            f"CREATE TRIGGER inmutable_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION proteger_egreso_append_only()"
        )


def downgrade():
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM movimientos_caja)
        OR EXISTS (SELECT 1 FROM reversos_pago_egreso)
        OR EXISTS (SELECT 1 FROM pagos_egreso)
        OR EXISTS (SELECT 1 FROM aperturas_caja)
        OR EXISTS (SELECT 1 FROM cuentas_caja)
        OR EXISTS (SELECT 1 FROM configuracion_aprobacion_egreso)
        OR EXISTS (SELECT 1 FROM historial_egreso)
        OR EXISTS (SELECT 1 FROM aprobaciones_egreso)
        OR EXISTS (SELECT 1 FROM documentos_financieros)
        OR EXISTS (SELECT 1 FROM egresos) THEN
          RAISE EXCEPTION 'Hay datos financieros; no se puede retirar CON-51/52';
        END IF;
        END $$"""
    )
    for table in (
        "movimientos_caja",
        "reversos_pago_egreso",
        "pagos_egreso",
        "aperturas_caja",
        "cuentas_caja",
        "configuracion_aprobacion_egreso",
        "historial_egreso",
        "aprobaciones_egreso",
        "documentos_financieros",
        "egresos",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION proteger_egreso_append_only()")
