"""Adaptador de persistencia SQLAlchemy para CON-2."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio


class CondominioRepository(Protocol):
    async def agregar(self, condominio: Condominio, auditoria: AuditoriaLogORM) -> Condominio: ...

    async def obtener_por_id(self, condominio_id: UUID) -> Condominio | None: ...


class SQLAlchemyCondominioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def agregar(self, condominio: Condominio, auditoria: AuditoriaLogORM) -> Condominio:
        self._session.add(condominio)
        await self._session.flush()
        self._session.add(auditoria)
        await self._session.flush()
        return condominio

    async def obtener_por_id(self, condominio_id: UUID) -> Condominio | None:
        resultado = await self._session.execute(
            select(Condominio).where(Condominio.id == condominio_id)
        )
        return resultado.scalar_one_or_none()
