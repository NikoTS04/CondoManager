"""Crear/adoptar catálogo de áreas y condiciones diarias (CON-39)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261020_0010"
down_revision = "20261020_0009"
branch_labels = None
depends_on = None
MARCA = "Creado por CON-39 / Alembic 20261020_0010"


def _validar_columnas():
    inspector = sa.inspect(op.get_bind())
    columnas = {c["name"]: c for c in inspector.get_columns("areas_comunes")}
    for nombre, tipo, nullable in (
        ("id", UUID(), False),
        ("condominio_id", UUID(), False),
        ("nombre", sa.String(100), False),
        ("descripcion", sa.Text(), True),
        ("aforo_maximo", sa.Integer(), False),
        ("costo_reserva", sa.Numeric(12, 2), False),
        ("esta_activa", sa.Boolean(), False),
    ):
        actual = columnas.get(nombre)
        if (
            actual is None
            or actual["nullable"] != nullable
            or actual["type"].compile(dialect=op.get_bind().dialect)
            != tipo.compile(dialect=op.get_bind().dialect)
        ):
            raise RuntimeError(f"CON-39: esquema incompatible en areas_comunes.{nombre}.")
    if inspector.get_pk_constraint("areas_comunes")["constrained_columns"] != ["id"]:
        raise RuntimeError("CON-39: falta la clave primaria UUID de áreas.")
    if {"hora_apertura", "hora_cierre"} & columnas.keys():
        raise RuntimeError("CON-39: las horas ya existen fuera de esta migración.")
    return columnas


def _validar_fk(campo, tabla, ondelete):
    inspector = sa.inspect(op.get_bind())
    if not any(
        fk["constrained_columns"] == [campo]
        and fk["referred_table"] == tabla
        and fk["referred_columns"] == ["id"]
        and fk.get("referred_schema") in (None, "public", inspector.default_schema_name)
        and fk.get("options", {}).get("ondelete") == ondelete
        for fk in inspector.get_foreign_keys("areas_comunes")
    ):
        raise RuntimeError(f"CON-39: FK incompatible en areas_comunes.{campo}.")


def upgrade():
    if "areas_comunes" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "areas_comunes",
            sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "condominio_id",
                UUID(),
                sa.ForeignKey("condominios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("nombre", sa.String(100), nullable=False),
            sa.Column("descripcion", sa.Text()),
            sa.Column("aforo_maximo", sa.Integer(), nullable=False),
            sa.Column("costo_reserva", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("esta_activa", sa.Boolean(), nullable=False, server_default=sa.true()),
            comment=MARCA,
        )
        op.execute("ALTER TABLE areas_comunes ENABLE ROW LEVEL SECURITY")
    columnas = _validar_columnas()
    _validar_fk("condominio_id", "condominios", "CASCADE")
    if "edificio_id" not in columnas:
        op.add_column(
            "areas_comunes",
            sa.Column(
                "edificio_id",
                UUID(),
                sa.ForeignKey(
                    "edificios.id", name="fk_area_catalogo_edificio", ondelete="SET NULL"
                ),
            ),
        )
    elif not columnas["edificio_id"]["nullable"] or not isinstance(
        columnas["edificio_id"]["type"], UUID
    ):
        raise RuntimeError("CON-39: edificio_id debe ser UUID nullable.")
    _validar_fk("edificio_id", "edificios", "SET NULL")
    if "tiempo_maximo_horas" not in columnas:
        op.add_column(
            "areas_comunes",
            sa.Column("tiempo_maximo_horas", sa.Integer(), nullable=False, server_default="4"),
        )
    elif columnas["tiempo_maximo_horas"]["nullable"] or not isinstance(
        columnas["tiempo_maximo_horas"]["type"], sa.Integer
    ):
        raise RuntimeError("CON-39: duración máxima incompatible.")
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM areas_comunes a JOIN edificios e ON a.edificio_id=e.id WHERE a.condominio_id<>e.condominio_id)"
        )
    ):
        raise RuntimeError("CON-39: existen áreas y edificios de condominios distintos.")
    checks = {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints("areas_comunes")}
    for nombre, expresion in (
        ("ck_area_aforo", "aforo_maximo > 0"),
        ("ck_area_costo", "costo_reserva >= 0.00"),
        ("ck_area_tiempo_maximo", "tiempo_maximo_horas >= 1"),
    ):
        if nombre not in checks:
            op.create_check_constraint(nombre, "areas_comunes", expresion)
    op.add_column(
        "areas_comunes",
        sa.Column("hora_apertura", sa.Time(), nullable=False, server_default="00:00"),
    )
    op.add_column(
        "areas_comunes", sa.Column("hora_cierre", sa.Time(), nullable=False, server_default="23:59")
    )
    op.create_check_constraint(
        "ck_area_horario_catalogo",
        "areas_comunes",
        "hora_cierre > hora_apertura AND EXTRACT(SECOND FROM hora_apertura) = 0 AND EXTRACT(SECOND FROM hora_cierre) = 0",
    )
    op.create_index(
        "idx_areas_catalogo_contexto", "areas_comunes", ["condominio_id", "esta_activa", "nombre"]
    )


def downgrade():
    propia = sa.inspect(op.get_bind()).get_table_comment("areas_comunes").get("text") == MARCA
    tiene_datos = op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM areas_comunes)"))
    referenciada = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE contype='f' AND confrelid='areas_comunes'::regclass)"
        )
    )
    op.drop_index("idx_areas_catalogo_contexto", table_name="areas_comunes")
    op.drop_constraint("ck_area_horario_catalogo", "areas_comunes", type_="check")
    op.drop_column("areas_comunes", "hora_cierre")
    op.drop_column("areas_comunes", "hora_apertura")
    if propia and not tiene_datos and not referenciada:
        op.drop_table("areas_comunes")
