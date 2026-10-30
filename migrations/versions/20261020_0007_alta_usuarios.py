"""Crear/adoptar identidad y habilitación administrativa (CON-04)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261020_0007"
down_revision = "20261019_0006"
branch_labels = None
depends_on = None
MARCA = "Creado por CON-04 / Alembic 20261020_0007"


def _id():
    return sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _validar(tabla, columnas, unicos=(), referencias=(), checks=()):
    inspector = sa.inspect(op.get_bind())
    reales = {c["name"]: c for c in inspector.get_columns(tabla)}
    dialect = op.get_bind().dialect
    for campo, tipo, nullable in columnas:
        actual = reales.get(campo)
        if (
            actual is None
            or actual["nullable"] != nullable
            or (actual["type"].compile(dialect=dialect) != tipo.compile(dialect=dialect))
        ):
            raise RuntimeError(f"CON-04: esquema incompatible en {tabla}.{campo}.")
    if inspector.get_pk_constraint(tabla)["constrained_columns"] != ["id"]:
        raise RuntimeError(f"CON-04: falta la PK de {tabla}.")
    existentes = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(tabla)}
    if any(clave not in existentes for clave in unicos):
        raise RuntimeError(f"CON-04: unicidad incompatible en {tabla}.")
    for campo, destino in referencias:
        if not any(
            fk["constrained_columns"] == [campo]
            and fk["referred_table"] == destino
            and fk["referred_columns"] == ["id"]
            and fk.get("referred_schema") in (None, "public")
            and fk.get("options", {}).get("ondelete") == "CASCADE"
            for fk in inspector.get_foreign_keys(tabla)
        ):
            raise RuntimeError(f"CON-04: FK incompatible en {tabla}.{campo}.")
    expresiones = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints(tabla)}
    for nombre, valores in checks:
        expresion = expresiones.get(nombre, "")
        if any(f"'{valor}'" not in expresion for valor in valores):
            raise RuntimeError(f"CON-04: catálogo incompatible en {tabla}.{nombre}.")


def upgrade():
    tablas = sa.inspect(op.get_bind()).get_table_names()
    if "usuarios" not in tablas:
        op.create_table(
            "usuarios",
            _id(),
            sa.Column("email", sa.String(120), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("nombre", sa.String(80), nullable=False),
            sa.Column("apellido", sa.String(80), nullable=False),
            sa.Column("telefono", sa.String(20)),
            sa.Column("documento_identidad", sa.String(20), nullable=False),
            sa.Column("esta_activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            comment=MARCA,
        )
    else:
        _validar(
            "usuarios",
            [
                ("id", UUID(), False),
                ("email", sa.String(120), False),
                ("password_hash", sa.String(255), False),
                ("nombre", sa.String(80), False),
                ("apellido", sa.String(80), False),
                ("telefono", sa.String(20), True),
                ("documento_identidad", sa.String(20), False),
                ("esta_activo", sa.Boolean(), False),
                ("creado_en", sa.DateTime(timezone=True), False),
            ],
            unicos=(("email",),),
        )
    columnas = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("usuarios")}
    if {"auth_revision", "es_superadmin"} & columnas:
        raise RuntimeError("CON-04: columnas de identidad ya existen fuera de esta migración.")
    for campo, expresion in (
        ("email", "lower(btrim(email))"),
        ("documento_identidad", "upper(btrim(documento_identidad))"),
    ):
        if op.get_bind().scalar(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM usuarios GROUP BY {expresion} HAVING count(*) > 1)"
            )
        ):
            raise RuntimeError(
                f"CON-04: duplicados históricos normalizados de {campo}; revisar antes de migrar."
            )
    op.alter_column("usuarios", "esta_activo", server_default=sa.false())
    op.add_column(
        "usuarios", sa.Column("auth_revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "usuarios",
        sa.Column("es_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint("ck_usuario_auth_revision", "usuarios", "auth_revision >= 1")
    op.create_index(
        "uq_usuario_email_normalizado", "usuarios", [sa.text("lower(btrim(email))")], unique=True
    )
    op.create_index(
        "uq_usuario_documento_normalizado",
        "usuarios",
        [sa.text("upper(btrim(documento_identidad))")],
        unique=True,
    )

    if "usuario_roles" not in tablas:
        op.create_table(
            "usuario_roles",
            _id(),
            sa.Column(
                "usuario_id",
                UUID(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "condominio_id",
                UUID(),
                sa.ForeignKey("condominios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("rol", sa.String(30), nullable=False, server_default="RESIDENTE"),
            sa.UniqueConstraint("usuario_id", "condominio_id", name="uq_usuario_condo_rol"),
            sa.CheckConstraint(
                "rol IN ('SUPERADMIN', 'ADMIN_JUNTA', 'AUDITOR', 'RESIDENTE')", name="ck_rol_nombre"
            ),
            comment=MARCA,
        )
    else:
        _validar(
            "usuario_roles",
            [
                ("id", UUID(), False),
                ("usuario_id", UUID(), False),
                ("condominio_id", UUID(), False),
                ("rol", sa.String(30), False),
            ],
            (("usuario_id", "condominio_id"),),
            (("usuario_id", "usuarios"), ("condominio_id", "condominios")),
            (("ck_rol_nombre", ("SUPERADMIN", "ADMIN_JUNTA", "AUDITOR", "RESIDENTE")),),
        )
    if "usuario_departamentos" not in tablas:
        op.create_table(
            "usuario_departamentos",
            _id(),
            sa.Column(
                "usuario_id",
                UUID(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "departamento_id",
                UUID(),
                sa.ForeignKey("departamentos.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "tipo_relacion", sa.String(30), nullable=False, server_default="PROPIETARIO_TITULAR"
            ),
            sa.Column("es_activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("usuario_id", "departamento_id", name="uq_usuario_depto"),
            sa.CheckConstraint(
                "tipo_relacion IN ('PROPIETARIO_TITULAR', 'INQUILINO', 'COPROPIETARIO')",
                name="ck_tipo_relacion",
            ),
            comment=MARCA,
        )
    else:
        _validar(
            "usuario_departamentos",
            [
                ("id", UUID(), False),
                ("usuario_id", UUID(), False),
                ("departamento_id", UUID(), False),
                ("tipo_relacion", sa.String(30), False),
                ("es_activo", sa.Boolean(), False),
            ],
            (("usuario_id", "departamento_id"),),
            (("usuario_id", "usuarios"), ("departamento_id", "departamentos")),
            (("ck_tipo_relacion", ("PROPIETARIO_TITULAR", "INQUILINO", "COPROPIETARIO")),),
        )
    for tabla in ("usuarios", "usuario_roles", "usuario_departamentos"):
        if tabla not in tablas:
            op.execute(sa.text(f'ALTER TABLE "{tabla}" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    propias = {
        tabla
        for tabla in ("usuarios", "usuario_roles", "usuario_departamentos")
        if inspector.get_table_comment(tabla).get("text") == MARCA
    }
    op.drop_index("uq_usuario_documento_normalizado", table_name="usuarios")
    op.drop_index("uq_usuario_email_normalizado", table_name="usuarios")
    op.drop_constraint("ck_usuario_auth_revision", "usuarios", type_="check")
    op.drop_column("usuarios", "es_superadmin")
    op.drop_column("usuarios", "auth_revision")
    op.alter_column("usuarios", "esta_activo", server_default=sa.true())
    for tabla in ("usuario_departamentos", "usuario_roles", "usuarios"):
        if tabla in propias:
            op.drop_table(tabla)
