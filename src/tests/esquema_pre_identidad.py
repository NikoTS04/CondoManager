"""Ensayos de reparadores históricos contra el contrato SQL anterior a CON-76."""

from importlib import import_module
from types import SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData

from scripts import reconciliar_esquema_20261026, reconciliar_esquema_legacy


async def fijar_esquema_pre_identidad(conn, monkeypatch):
    def preparar(connection):
        with Operations.context(MigrationContext.configure(connection)):
            import_module("migrations.versions.20261113_0021_invitaciones_identidad").downgrade()
        # Fuente independiente del ORM actual: esquema canónico construido por migraciones.
        esperado = MetaData()
        esperado.reflect(connection)
        return esperado

    esperado = await conn.run_sync(preparar)
    monkeypatch.setattr(reconciliar_esquema_legacy, "Base", SimpleNamespace(metadata=esperado))

    def modelo_historico(modelo):
        return SimpleNamespace(
            __tablename__=modelo.__tablename__, __table__=esperado.tables[modelo.__tablename__]
        )

    # El script legacy crea estas tablas a partir del modelo de su propio corte.
    anteriores = reconciliar_esquema_legacy.NUEVAS
    monkeypatch.setattr(
        reconciliar_esquema_legacy, "NUEVAS", tuple(modelo_historico(m) for m in anteriores)
    )
    monkeypatch.setattr(
        reconciliar_esquema_legacy, "Notificacion", reconciliar_esquema_legacy.NUEVAS[1]
    )
    monkeypatch.setattr(
        reconciliar_esquema_20261026,
        "ADOPTADAS",
        tuple(modelo_historico(m) for m in reconciliar_esquema_20261026.ADOPTADAS),
    )
