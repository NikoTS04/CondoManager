"""Directorio de proveedores y repositorio de contratos y pólizas (CON-48, CON-49)."""

import sqlalchemy as sa
from alembic import op

revision = "20261201_0031"
down_revision = "20261130_0030"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Tabla proveedores (CON-48)
    op.create_table(
        "proveedores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("condominio_id", sa.Uuid(), nullable=False),
        sa.Column("ruc", sa.String(length=11), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.Column("nombre_comercial", sa.String(length=200), nullable=True),
        sa.Column("rubro", sa.String(length=100), nullable=False),
        sa.Column("contacto_nombre", sa.String(length=150), nullable=False),
        sa.Column("contacto_telefono", sa.String(length=50), nullable=False),
        sa.Column("contacto_email", sa.String(length=120), nullable=False),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["condominio_id"], ["condominios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("condominio_id", "ruc", name="uq_proveedor_condominio_ruc"),
        sa.CheckConstraint("length(ruc) = 11", name="ck_proveedor_ruc_longitud"),
        sa.CheckConstraint("version >= 1", name="ck_proveedor_version"),
    )
    op.create_index("ix_proveedores_condominio_id", "proveedores", ["condominio_id"])
    op.create_index("ix_proveedores_ruc", "proveedores", ["ruc"])

    # 2. Tabla contratos_proveedor (CON-49)
    op.create_table(
        "contratos_proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("condominio_id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("numero_contrato", sa.String(length=100), nullable=False),
        sa.Column("tipo_documento", sa.String(length=50), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("monto_mensual", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("moneda", sa.String(length=3), nullable=False, server_default="PEN"),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("contacto_emergencia", sa.String(length=150), nullable=True),
        sa.Column("contacto_emergencia_telefono", sa.String(length=50), nullable=True),
        sa.Column("estado", sa.String(length=30), nullable=False, server_default="VIGENTE"),
        sa.Column("version_actual", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["condominio_id"], ["condominios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("fecha_fin >= fecha_inicio", name="ck_contrato_fechas"),
        sa.CheckConstraint(
            "tipo_documento IN ('CONTRATO_SERVICIO', 'POLIZA_SEGURO', 'ADDENDA', 'ACTA_CONFORMIDAD')",
            name="ck_contrato_tipo_documento",
        ),
        sa.CheckConstraint(
            "estado IN ('VIGENTE', 'POR_VENCER', 'VENCIDO', 'RENOVADO', 'CANCELADO')",
            name="ck_contrato_estado",
        ),
        sa.CheckConstraint("version_actual >= 1", name="ck_contrato_version_actual"),
    )
    op.create_index(
        "ix_contratos_proveedor_condominio_id", "contratos_proveedor", ["condominio_id"]
    )
    op.create_index("ix_contratos_proveedor_proveedor_id", "contratos_proveedor", ["proveedor_id"])
    op.create_index("ix_contratos_proveedor_fecha_fin", "contratos_proveedor", ["fecha_fin"])

    # 3. Tabla documentos_contrato_version (CON-49)
    op.create_table(
        "documentos_contrato_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archivo_nombre", sa.String(length=255), nullable=False),
        sa.Column("archivo_mime", sa.String(length=100), nullable=False),
        sa.Column("archivo_tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("archivo_binario", sa.LargeBinary(), nullable=False),
        sa.Column("motivo_reemplazo", sa.Text(), nullable=True),
        sa.Column("subido_por", sa.Uuid(), nullable=False),
        sa.Column(
            "subido_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos_proveedor.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subido_por"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("contrato_id", "version", name="uq_documento_contrato_version"),
        sa.CheckConstraint("version >= 1", name="ck_doc_version_positiva"),
        sa.CheckConstraint("archivo_tamano_bytes > 0", name="ck_doc_tamano_positivo"),
    )
    op.create_index(
        "ix_documentos_contrato_version_contrato_id",
        "documentos_contrato_version",
        ["contrato_id"],
    )


def downgrade():
    op.drop_table("documentos_contrato_version")
    op.drop_table("contratos_proveedor")
    op.drop_table("proveedores")
