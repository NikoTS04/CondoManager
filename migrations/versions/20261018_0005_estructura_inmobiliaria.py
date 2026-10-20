"""Crear/adoptar estructura inmobiliaria de Supabase y añadir activo (CON-3).

Las tablas preexistentes se verifican, no se recrean. El comentario de procedencia
permite que el downgrade conserve esas tablas y complete el ciclo en bases nuevas.
"""

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261018_0005"
down_revision = "20261014_0004"
branch_labels = None
depends_on = None
MARCA = "Creado por CON-3 / Alembic 20261018_0005"


def _validar_existente(nombre, columnas, unicos, referencia, checks):
    inspector = sa.inspect(op.get_bind())
    reales = {c["name"]: c for c in inspector.get_columns(nombre)}
    for campo, tipo in columnas.items():
        actual = reales.get(campo)
        if actual is None or str(actual["type"]).upper() != tipo or actual["nullable"]:
            raise RuntimeError(
                f"CON-3: esquema incompatible en {nombre}.{campo}; revisar baseline."
            )
    if set(inspector.get_pk_constraint(nombre)["constrained_columns"]) != {"id"}:
        raise RuntimeError(f"CON-3: falta PK UUID en {nombre}.")
    claves = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(nombre)}
    if unicos not in claves:
        raise RuntimeError(f"CON-3: falta unicidad {nombre}{unicos}.")
    columna, destino = referencia
    if not any(
        fk["constrained_columns"] == [columna]
        and fk["referred_table"] == destino
        and fk["referred_columns"] == ["id"]
        and fk.get("referred_schema") in (None, "public")
        and fk.get("options", {}).get("ondelete") == "CASCADE"
        for fk in inspector.get_foreign_keys(nombre)
    ):
        raise RuntimeError(f"CON-3: relación incompatible en {nombre}.{columna}.")
    restricciones = {
        c["name"]: re.sub(r"[\s()]", "", c["sqltext"]).lower()
        for c in inspector.get_check_constraints(nombre)
    }
    for clave, expresion in checks.items():
        if restricciones.get(clave) != re.sub(r"[\s()]", "", expresion).lower():
            raise RuntimeError(f"CON-3: check incompatible {nombre}.{clave}.")
    if nombre == "departamentos":
        estado = restricciones.get("ck_departamento_estado_financiero", "")
        if not all(f"'{valor}'" in estado for valor in ("al_dia", "observado", "en_mora")):
            raise RuntimeError("CON-3: estados financieros incompatibles.")


def upgrade():
    tablas = sa.inspect(op.get_bind()).get_table_names()
    if "edificios" not in tablas:
        op.create_table(
            "edificios",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "condominio_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("condominios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("nombre_bloque", sa.String(100), nullable=False),
            sa.Column("total_pisos", sa.Integer(), nullable=False),
            sa.UniqueConstraint(
                "condominio_id", "nombre_bloque", name="uq_edificio_condominio_bloque"
            ),
            sa.CheckConstraint("total_pisos >= 1", name="ck_edificio_pisos"),
            comment=MARCA,
        )
    else:
        _validar_existente(
            "edificios",
            {
                "id": "UUID",
                "condominio_id": "UUID",
                "nombre_bloque": "VARCHAR(100)",
                "total_pisos": "INTEGER",
            },
            ("condominio_id", "nombre_bloque"),
            ("condominio_id", "condominios"),
            {"ck_edificio_pisos": "total_pisos >= 1"},
        )
    if "departamentos" not in tablas:
        op.create_table(
            "departamentos",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "edificio_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("edificios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("numero", sa.String(20), nullable=False),
            sa.Column("piso", sa.SmallInteger(), nullable=False),
            sa.Column("coeficiente_participacion", sa.Numeric(7, 4), nullable=False),
            sa.Column("saldo_a_favor", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("estado_financiero", sa.String(20), nullable=False, server_default="AL_DIA"),
            sa.UniqueConstraint("edificio_id", "numero", name="uq_edificio_departamento"),
            sa.CheckConstraint("piso >= 1", name="ck_departamento_piso"),
            sa.CheckConstraint(
                "coeficiente_participacion > 0.0000", name="ck_departamento_coeficiente"
            ),
            sa.CheckConstraint("saldo_a_favor >= 0.00", name="ck_departamento_saldo_favor"),
            sa.CheckConstraint(
                "estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA')",
                name="ck_departamento_estado_financiero",
            ),
            comment=MARCA,
        )
    else:
        _validar_existente(
            "departamentos",
            {
                "id": "UUID",
                "edificio_id": "UUID",
                "numero": "VARCHAR(20)",
                "piso": "SMALLINT",
                "coeficiente_participacion": "NUMERIC(7, 4)",
                "saldo_a_favor": "NUMERIC(12, 2)",
                "estado_financiero": "VARCHAR(20)",
            },
            ("edificio_id", "numero"),
            ("edificio_id", "edificios"),
            {
                "ck_departamento_piso": "piso >= 1",
                "ck_departamento_coeficiente": "coeficiente_participacion > 0.0000",
                "ck_departamento_saldo_favor": "saldo_a_favor >= 0.00",
            },
        )
    # No adoptar una columna de origen desconocido: esta revisión la crea y la revierte.
    if "activo" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("departamentos")}:
        raise RuntimeError("CON-3: activo ya existe fuera de esta migración; revisar baseline.")
    op.add_column(
        "departamentos", sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.create_check_constraint(
        "ck_departamento_coeficiente_maximo",
        "departamentos",
        "coeficiente_participacion <= 100.0000",
    )
    for tabla, indice, campo in (
        ("edificios", "idx_edificios_condominio", "condominio_id"),
        ("departamentos", "idx_departamentos_edificio", "edificio_id"),
    ):
        if indice not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(tabla)}:
            op.create_index(indice, tabla, [campo])
    op.create_index(
        "uq_edificio_nombre_normalizado",
        "edificios",
        ["condominio_id", sa.text("lower(btrim(nombre_bloque))")],
        unique=True,
    )
    op.create_index(
        "uq_departamento_numero_normalizado",
        "departamentos",
        ["edificio_id", sa.text("upper(btrim(numero))")],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_departamento_numero_normalizado", table_name="departamentos")
    op.drop_index("uq_edificio_nombre_normalizado", table_name="edificios")
    op.drop_constraint("ck_departamento_coeficiente_maximo", "departamentos", type_="check")
    op.drop_column("departamentos", "activo")
    for tabla in ("departamentos", "edificios"):
        if sa.inspect(op.get_bind()).get_table_comment(tabla).get("text") == MARCA:
            op.drop_table(tabla)
