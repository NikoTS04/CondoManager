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
    bind = op.get_bind()
    if bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM revisiones_pago WHERE notas_internas IS NOT NULL)")
    ):
        raise RuntimeError("CON-72: existen notas internas; restaurar copia verificada.")
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT comprobante_id FROM archivos_voucher "
            "WHERE comprobante_id IS NOT NULL GROUP BY comprobante_id HAVING count(*) > 1)"
        )
    ):
        raise RuntimeError("CON-72: existen versiones de evidencia; restaurar copia verificada.")
    op.drop_constraint("fk_revision_archivo", "revisiones_pago", type_="foreignkey")
    op.drop_column("revisiones_pago", "notas_internas")
    op.drop_column("revisiones_pago", "archivo_nombre")
    op.create_unique_constraint(
        "archivos_voucher_comprobante_id_key", "archivos_voucher", ["comprobante_id"]
    )
