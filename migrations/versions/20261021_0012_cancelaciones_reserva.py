"""Cancelación persistente de CON-46 sobre la tabla compartida de reservas."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20261021_0012"
down_revision = "20261020_0012"
branch_labels = None
depends_on = None
MARCA = "CON-46 / Alembic 20261021_0012"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "reservas" not in inspector.get_table_names():
        op.create_table(
            "reservas",
            sa.Column("id", UUID(), primary_key=True),
            sa.Column(
                "area_id",
                UUID(),
                sa.ForeignKey("areas_comunes.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "departamento_id",
                UUID(),
                sa.ForeignKey("departamentos.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "usuario_id",
                UUID(),
                sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
                nullable=False,
            ),
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
            sa.CheckConstraint("hora_fin > hora_inicio", name="ck_reserva_horario"),
            sa.CheckConstraint("costo_reserva >= 0", name="ck_reserva_costo"),
            sa.CheckConstraint(
                "estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA')",
                name="ck_reserva_estado",
            ),
            comment=MARCA,
        )
        op.execute("ALTER TABLE reservas ENABLE ROW LEVEL SECURITY")
    # Adoptar el modelo histórico sin reinterpretar horas ni eliminar registros.
    columnas = {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns("reservas")}
    for nombre, tipo in (
        ("id", UUID()),
        ("area_id", UUID()),
        ("departamento_id", UUID()),
        ("usuario_id", UUID()),
        ("fecha_reserva", sa.Date()),
        ("hora_inicio", sa.Time()),
        ("hora_fin", sa.Time()),
        ("costo_reserva", sa.Numeric(12, 2)),
        ("estado", sa.String(20)),
        ("creado_en", sa.DateTime(timezone=True)),
    ):
        actual = columnas.get(nombre)
        if (
            actual is None
            or (actual["nullable"] and nombre != "usuario_id")
            or (
                actual["type"].compile(dialect=op.get_bind().dialect)
                != tipo.compile(dialect=op.get_bind().dialect)
            )
        ):
            raise RuntimeError(f"CON-46: esquema incompatible en reservas.{nombre}.")
    inspector = sa.inspect(op.get_bind())
    if inspector.get_pk_constraint("reservas")["constrained_columns"] != ["id"]:
        raise RuntimeError("CON-46: reservas requiere clave primaria UUID.")
    for campo, tabla in (
        ("area_id", "areas_comunes"),
        ("departamento_id", "departamentos"),
        ("usuario_id", "usuarios"),
    ):
        if not any(
            fk["constrained_columns"] == [campo]
            and fk["referred_table"] == tabla
            and fk["referred_columns"] == ["id"]
            for fk in inspector.get_foreign_keys("reservas")
        ):
            raise RuntimeError(f"CON-46: falta integridad referencial de reservas.{campo}.")
    conocidas = {
        "id",
        "area_id",
        "departamento_id",
        "usuario_id",
        "fecha_reserva",
        "hora_inicio",
        "hora_fin",
        "costo_reserva",
        "estado",
        "creado_en",
        "zona_horaria",
        # Extensión de CON-73, previa a esta revisión.
        "condominio_id",
        "moneda",
        "area_nombre",
        "fecha_cancelacion",
        "cancelado_por",
        "motivo_cancelacion",
    }
    for nombre, columna in columnas.items():
        if (
            nombre not in conocidas
            and not columna["nullable"]
            and columna.get("default") is None
            and not columna.get("identity")
            and not columna.get("computed")
        ):
            raise RuntimeError(f"CON-46: columna obligatoria no contemplada en reservas.{nombre}.")
    if "zona_horaria" not in columnas:
        op.add_column(
            "reservas",
            sa.Column(
                "zona_horaria",
                sa.String(30),
                nullable=False,
                server_default="UTC",
                comment=MARCA,
            ),
        )
    elif columnas["zona_horaria"]["nullable"] or not isinstance(
        columnas["zona_horaria"]["type"], sa.String
    ):
        raise RuntimeError("CON-46: zona_horaria incompatible.")
    if "ck_reserva_zona" not in {c["name"] for c in inspector.get_check_constraints("reservas")}:
        op.create_check_constraint(
            "ck_reserva_zona", "reservas", "zona_horaria IN ('UTC', 'America/Lima')"
        )
    op.create_table(
        "cobros_reserva",
        sa.Column(
            "reserva_id",
            UUID(),
            sa.ForeignKey("reservas.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "comprobante_id",
            UUID(),
            sa.ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_compensado", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("reembolsable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("monto > 0", name="ck_cobro_reserva_monto"),
        sa.CheckConstraint(
            "monto_compensado >= 0 AND monto_compensado <= monto",
            name="ck_cobro_reserva_compensado",
        ),
    )
    op.create_table(
        "cancelaciones_reserva",
        sa.Column(
            "reserva_id",
            UUID(),
            sa.ForeignKey("reservas.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("actor_id", UUID(), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("fecha_cancelacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resultado", JSONB(), nullable=False),
    )
    if "eventos_reserva_outbox" not in inspector.get_table_names():
        op.create_table(
            "eventos_reserva_outbox",
            sa.Column("id", UUID(), primary_key=True),
            sa.Column(
                "reserva_id",
                UUID(),
                sa.ForeignKey("reservas.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "tipo", sa.String(60), nullable=False, server_default="ReservaCanceladaEvent"
            ),
            sa.Column("payload", JSONB(), nullable=False),
            sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
            sa.Column("publicado_en", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("reserva_id", "tipo", name="uq_evento_reserva_tipo"),
            comment=MARCA,
        )
        op.create_index(
            "idx_evento_reserva_pendiente", "eventos_reserva_outbox", ["publicado_en", "creado_en"]
        )
        op.execute("ALTER TABLE eventos_reserva_outbox ENABLE ROW LEVEL SECURITY")
    else:
        # Cola creada por CON-73 sin tipo: se deduce del sobre del evento ya persistido.
        op.add_column(
            "eventos_reserva_outbox",
            sa.Column(
                "tipo",
                sa.String(60),
                nullable=False,
                server_default="ReservaCanceladaEvent",
                comment=MARCA,
            ),
        )
        op.execute(
            "UPDATE eventos_reserva_outbox SET tipo = payload->>'event_type' "
            "WHERE payload->>'event_type' IS NOT NULL"
        )
        op.create_unique_constraint(
            "uq_evento_reserva_tipo", "eventos_reserva_outbox", ["reserva_id", "tipo"]
        )
    # Las tablas existentes de Supabase ya tienen RLS. Las nuevas siguen esa
    # protección; el acceso del backend conserva el rol de conexión existente.
    for tabla in ("cobros_reserva", "cancelaciones_reserva"):
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def outbox_creada(inspector):
    return inspector.get_table_comment("eventos_reserva_outbox").get("text") == MARCA


def downgrade():
    inspector = sa.inspect(op.get_bind())
    # El rollback del esquema no debe borrar una cancelación confirmada ni
    # reinterpretar como UTC una reserva local ya registrada.
    for tabla in ("eventos_reserva_outbox", "cancelaciones_reserva", "cobros_reserva"):
        if tabla == "eventos_reserva_outbox" and not outbox_creada(inspector):
            continue
        if op.get_bind().scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {tabla})")):
            raise RuntimeError("CON-46: el downgrade requiere tablas de cancelación vacías.")
    inspector = sa.inspect(op.get_bind())
    creada = inspector.get_table_comment("reservas")["text"] == MARCA
    zona = next(c for c in inspector.get_columns("reservas") if c["name"] == "zona_horaria")
    if creada and op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM reservas)")):
        raise RuntimeError("CON-46: no se elimina una tabla de reservas con datos.")
    if zona.get("comment") == MARCA and op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM reservas WHERE zona_horaria <> 'UTC')")
    ):
        raise RuntimeError("CON-46: no se retira la zona de reservas locales existentes.")
    if outbox_creada(inspector):
        op.drop_table("eventos_reserva_outbox")
    else:
        op.drop_constraint("uq_evento_reserva_tipo", "eventos_reserva_outbox", type_="unique")
        op.drop_column("eventos_reserva_outbox", "tipo")
    op.drop_table("cancelaciones_reserva")
    op.drop_table("cobros_reserva")
    if creada:
        op.drop_table("reservas")
    else:
        if zona.get("comment") == MARCA:
            op.drop_constraint("ck_reserva_zona", "reservas", type_="check")
            op.drop_column("reservas", "zona_horaria")
