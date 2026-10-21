"""Repositorio de persistencia SQL para Comprobantes de Pago (CON-23 / PROC-02)."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.condominios.models import Departamento, Edificio
from src.modules.pagos.models import ComprobantePago


class PagosRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def obtener_por_id(self, comprobante_id: UUID) -> Optional[ComprobantePago]:
        return await self.session.get(ComprobantePago, comprobante_id)

    async def buscar_por_hash(self, idempotency_hash: str) -> Optional[ComprobantePago]:
        stmt = select(ComprobantePago).where(ComprobantePago.idempotency_hash == idempotency_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def listar_por_condominio(
        self, condominio_id: UUID, departamento_ids: Optional[List[UUID]] = None
    ) -> List[ComprobantePago]:
        stmt = (
            select(ComprobantePago)
            .join(Departamento, ComprobantePago.departamento_id == Departamento.id)
            .join(Edificio, Departamento.edificio_id == Edificio.id)
            .where(Edificio.condominio_id == condominio_id)
            .order_by(ComprobantePago.creado_en.desc())
        )
        if departamento_ids is not None:
            stmt = stmt.where(ComprobantePago.departamento_id.in_(departamento_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def guardar(self, comprobante: ComprobantePago) -> ComprobantePago:
        self.session.add(comprobante)
        try:
            await self.session.commit()
            await self.session.refresh(comprobante)
            return comprobante
        except IntegrityError:
            await self.session.rollback()
            raise


def get_pagos_repository(session: AsyncSession = Depends(get_db_session)) -> PagosRepository:
    return PagosRepository(session)
