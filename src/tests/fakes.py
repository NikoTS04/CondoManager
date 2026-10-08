"""Dobles de prueba compartidos por las verificaciones de CON-2."""

from uuid import UUID

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio


class FakeCondominioRepository:
    def __init__(self) -> None:
        self.condominios: dict[UUID, Condominio] = {}
        self.auditorias: list[AuditoriaLogORM] = []

    async def agregar(self, condominio: Condominio, auditoria: AuditoriaLogORM) -> Condominio:
        self.condominios[condominio.id] = condominio
        self.auditorias.append(auditoria)
        return condominio

    async def obtener_por_id(self, condominio_id: UUID) -> Condominio | None:
        return self.condominios.get(condominio_id)
