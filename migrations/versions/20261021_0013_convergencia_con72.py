"""CON-72: conservar versiones de evidencia y asociar revisiones sin reescribir hechos."""

import sqlalchemy as sa
from alembic import op

revision = "20261021_0013"
down_revision = "20261020_0012"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("archivos_voucher"):
        if constraint["column_names"] == ["comprobante_id"]:
            op.drop_constraint(constraint["name"], "archivos_voucher", type_="unique")
    op.add_column("revisiones_pago", sa.Column("archivo_nombre", sa.Text(), nullable=True))
    op.add_column("revisiones_pago", sa.Column("notas_internas", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_revision_archivo",
        "revisiones_pago",
        "archivos_voucher",
        ["archivo_nombre"],
        ["nombre"],
        ondelete="RESTRICT",
    )
    op.execute("""UPDATE revisiones_pago r SET archivo_nombre=a.nombre
        FROM archivos_voucher a WHERE a.comprobante_id=r.comprobante_id""")


def downgrade():
    raise RuntimeError(
        "CON-72: no eliminar versiones de evidencia ni notas; restaurar copia verificada."
    )
