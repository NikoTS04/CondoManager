"""CON-73: adoptar reservas y crear cola durable sin descartar históricos."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20261020_0012"
down_revision = "20261020_0011"
branch_labels = None
depends_on = None


def fk(tabla):
    return sa.ForeignKey(f"{tabla}.id", ondelete="RESTRICT")


def validar(tabla, campos):
    inspector = sa.inspect(op.get_bind())
    columnas = {c["name"]: c for c in inspector.get_columns(tabla)}
    for nombre, tipo, nullable in campos:
        actual = columnas.get(nombre)
        if (
            actual is None
            or actual["nullable"] != nullable
            or actual["type"].compile(dialect=op.get_bind().dialect)
            != tipo.compile(dialect=op.get_bind().dialect)
        ):
            raise RuntimeError(
                f"CON-73: esquema incompatible en {tabla}.{nombre}; no se borraron datos."
            )
    return columnas


def upgrade():
    if "reservas" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "reservas",
            sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("area_id", UUID(), fk("areas_comunes"), nullable=False),
            sa.Column("departamento_id", UUID(), fk("departamentos"), nullable=False),
            sa.Column("fecha_reserva", sa.Date(), nullable=False),
            sa.Column("hora_inicio", sa.Time(), nullable=False),
            sa.Column("hora_fin", sa.Time(), nullable=False),
            sa.Column("costo_reserva", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("estado", sa.String(20), nullable=False, server_default="SOLICITADA"),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    columnas = validar(
        "reservas",
        (
            ("id", UUID(), False),
            ("area_id", UUID(), False),
            ("departamento_id", UUID(), False),
            ("fecha_reserva", sa.Date(), False),
            ("hora_inicio", sa.Time(), False),
            ("hora_fin", sa.Time(), False),
            ("costo_reserva", sa.Numeric(12, 2), False),
            ("estado", sa.String(20), False),
            ("creado_en", sa.DateTime(timezone=True), False),
        ),
    )
    inspector = sa.inspect(op.get_bind())
    if inspector.get_pk_constraint("reservas")["constrained_columns"] != ["id"]:
        raise RuntimeError("CON-73: reservas requiere PK id.")
    for campo, tabla in (("area_id", "areas_comunes"), ("departamento_id", "departamentos")):
        if not any(
            f["constrained_columns"] == [campo]
            and f["referred_table"] == tabla
            and f["referred_columns"] == ["id"]
            and f.get("referred_schema") in (None, inspector.default_schema_name)
            and f.get("options", {}).get("ondelete") == "RESTRICT"
            for f in inspector.get_foreign_keys("reservas")
        ):
            raise RuntimeError(f"CON-73: FK incompatible en reservas.{campo}.")
    if op.get_bind().scalar(
        sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM reservas r JOIN areas_comunes a ON a.id=r.area_id
          JOIN departamentos d ON d.id=r.departamento_id JOIN edificios e ON e.id=d.edificio_id
          WHERE a.condominio_id<>e.condominio_id)
    """)
    ):
        raise RuntimeError(
            "CON-73: reservas históricas cruzan condominios; corrija antes de migrar."
        )
    if op.get_bind().scalar(
        sa.text("""
        SELECT EXISTS (SELECT 1 FROM reservas a JOIN reservas b
          ON a.area_id=b.area_id AND a.fecha_reserva=b.fecha_reserva AND a.id<b.id
          WHERE a.estado='CONFIRMADA' AND b.estado='CONFIRMADA'
            AND a.hora_inicio<b.hora_fin AND a.hora_fin>b.hora_inicio)
    """)
    ):
        raise RuntimeError(
            "CON-73: existen reservas confirmadas solapadas; concilie los históricos antes de migrar."
        )
    extensiones = [
        sa.Column("condominio_id", UUID(), fk("condominios")),
        sa.Column("usuario_id", UUID(), fk("usuarios")),
        sa.Column("moneda", sa.String(3)),
        sa.Column("area_nombre", sa.Text()),
        sa.Column("zona_horaria", sa.String(40)),
        sa.Column("fecha_cancelacion", sa.DateTime(timezone=True)),
        sa.Column("cancelado_por", UUID(), fk("usuarios")),
        sa.Column("motivo_cancelacion", sa.Text()),
    ]
    if any(c.name in columnas for c in extensiones):
        raise RuntimeError("CON-73: extensión de reservas preexistente sin revisión Alembic.")
    for columna in extensiones:
        op.add_column("reservas", columna)
    op.execute("""
        UPDATE reservas r SET condominio_id=a.condominio_id, moneda=c.moneda, zona_horaria='UTC', area_nombre=a.nombre
        FROM areas_comunes a JOIN condominios c ON c.id=a.condominio_id WHERE a.id=r.area_id
    """)
    for nombre in ("condominio_id", "moneda", "zona_horaria", "area_nombre"):
        op.alter_column("reservas", nombre, nullable=False)
    checks = {c["name"] for c in inspector.get_check_constraints("reservas")}
    for nombre, expresion in (
        ("ck_reserva_horario", "hora_fin > hora_inicio"),
        ("ck_reserva_costo", "costo_reserva >= 0"),
        (
            "ck_reserva_estado",
            "estado IN ('SOLICITADA','CONFIRMADA','RECHAZADA','CANCELADA','COMPLETADA')",
        ),
        ("ck_reserva_moneda", "moneda IN ('PEN','USD')"),
        ("ck_reserva_zona", "zona_horaria IN ('UTC','America/Lima')"),
    ):
        if nombre not in checks:
            op.create_check_constraint(nombre, "reservas", expresion)
    op.create_index(
        "idx_reservas_contexto_unidad", "reservas", ["condominio_id", "departamento_id"]
    )
    op.create_index("idx_reservas_area_fecha", "reservas", ["area_id", "fecha_reserva", "estado"])
    op.create_table(
        "bloqueos_area",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("area_id", UUID(), fk("areas_comunes"), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("fin > inicio", name="ck_bloqueo_intervalo"),
    )
    op.create_index("ix_bloqueos_area_area_id", "bloqueos_area", ["area_id"])
    op.create_table(
        "eventos_reserva_outbox",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("reserva_id", UUID(), fk("reservas"), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_eventos_reserva_outbox_reserva_id", "eventos_reserva_outbox", ["reserva_id"]
    )
    op.create_index(
        "idx_evento_reserva_pendiente", "eventos_reserva_outbox", ["publicado_en", "creado_en"]
    )
    # Una bitácora anterior sin identidad/evento no puede adoptarse inventando UUID.
    # DDL transaccional: si existe una tabla incompatible, todo el upgrade revierte.
    op.create_table(
        "notificaciones_logs",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("condominio_id", UUID(), fk("condominios"), nullable=False),
        sa.Column("departamento_id", UUID(), fk("departamentos"), nullable=False),
        sa.Column("usuario_destinatario_id", UUID(), fk("usuarios"), nullable=False),
        sa.Column("evento_id", UUID(), nullable=False),
        sa.Column("operacion_id", UUID(), nullable=False),
        sa.Column("tipo_evento", sa.Text(), nullable=False),
        sa.Column("canal", sa.String(20), nullable=False),
        sa.Column("destinatario", sa.Text(), nullable=False),
        sa.Column("asunto", sa.Text()),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False),
        sa.Column("transporte", sa.String(20), nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("intentos", sa.Integer(), nullable=False),
        sa.Column("proximo_reintento", sa.DateTime(timezone=True)),
        sa.Column("bloqueado_hasta", sa.DateTime(timezone=True)),
        sa.Column("proveedor_message_id", sa.Text()),
        sa.Column("error_mensaje", sa.Text()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "evento_id",
            "operacion_id",
            "usuario_destinatario_id",
            "canal",
            name="uq_notificacion_logica",
        ),
        sa.CheckConstraint(
            "intentos BETWEEN 0 AND 4 AND ciclo >= 1", name="ck_notificacion_intentos"
        ),
        sa.CheckConstraint(
            "estado IN ('EN_COLA','ENVIADO','ENTREGADO','REINTENTANDO','FALLIDO_PERMANENTE')",
            name="ck_notificacion_estado",
        ),
        sa.CheckConstraint(
            "transporte IN ('SIMULADO','PROVEEDOR')", name="ck_notificacion_transporte"
        ),
        sa.CheckConstraint(
            "canal IN ('EMAIL','WHATSAPP','SMS','PUSH')", name="ck_notificacion_canal"
        ),
    )
    op.create_index(
        "idx_notificacion_contexto_usuario",
        "notificaciones_logs",
        ["condominio_id", "usuario_destinatario_id"],
    )
    op.create_index(
        "idx_notificacion_pendiente", "notificaciones_logs", ["estado", "proximo_reintento"]
    )
    op.create_table(
        "notificaciones_intentos",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("notificacion_id", UUID(), fk("notificaciones_logs"), nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("iniciado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminado_en", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("proveedor_message_id", sa.Text()),
        sa.UniqueConstraint("notificacion_id", "ciclo", "numero", name="uq_notificacion_intento"),
        sa.CheckConstraint("numero BETWEEN 1 AND 4 AND ciclo >= 1", name="ck_intento_numero"),
    )
    op.create_table(
        "notificaciones_eventos",
        sa.Column("consumidor", sa.Text(), primary_key=True),
        sa.Column("event_id", UUID(), primary_key=True),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notificaciones_incidencias",
        sa.Column("clave", sa.Text(), primary_key=True),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    for tabla in (
        "reservas",
        "bloqueos_area",
        "eventos_reserva_outbox",
        "notificaciones_logs",
        "notificaciones_intentos",
        "notificaciones_eventos",
        "notificaciones_incidencias",
    ):
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade():
    raise RuntimeError(
        "CON-73: downgrade destructivo deshabilitado; restaurar una copia verificada."
    )
