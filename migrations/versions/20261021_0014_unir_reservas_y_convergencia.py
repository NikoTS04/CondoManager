"""Unir CON-46 (cancelaciones) y CON-72 (convergencia de evidencia) en una sola cabeza."""

revision = "20261021_0014"
down_revision = ("20261021_0012", "20261021_0013")
branch_labels = None
depends_on = None


def upgrade():
    # Ambas ramas parten de 20261020_0012 y tocan tablas distintas; no hay DDL de conciliación.
    pass


def downgrade():
    pass
