"""Repositorios de persistencia y consultas financieras para Pagos y Comprobantes.

Soporta CON-23 (Deduplicación de Comprobantes - Brandon) y CON-22/70 (Persistencia y Vouchers - Anderson).
"""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditoriaPayload
from src.core.authorization import (
    autorizar_departamento,
    denegar,
    puede_ver_departamento,
)
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.pagos.models import ComprobantePago


class PagosRepository:
    """Repositorio de persistencia SQL para Comprobantes de Pago (CON-23 / PROC-02)."""

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


class SQLAlchemyPagosRepository:
    """Consultas y locks financieros compatibles con CON-11/13/22 y la identidad vigente."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def departamento(self, did: UUID, usuario: dict, *, escritura=False, bloquear=False):
        if usuario.get("rol") == "AUDITOR" and escritura:
            denegar("El auditor tiene permisos de solo lectura.")
        if not puede_ver_departamento(usuario, did):
            denegar("El departamento no pertenece a sus vínculos activos.")
        row = (
            await self.session.execute(
                select(Departamento, Condominio)
                .join(Edificio, Departamento.edificio_id == Edificio.id)
                .join(Condominio, Edificio.condominio_id == Condominio.id)
                .where(Departamento.id == did)
            )
        ).one_or_none()
        if row is None:
            raise APIError(404, "DEPARTAMENTO_NO_ENCONTRADO", "No existe el departamento.")
        depto, condominio = row
        autorizar_departamento(usuario, did, condominio.id, escritura=escritura)
        if bloquear:
            # Orden único: condominio -> departamento -> cuotas -> comprobante/subida.
            condominio = await self.session.scalar(
                select(Condominio)
                .where(Condominio.id == condominio.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            depto = await self.session.scalar(
                select(Departamento)
                .where(Departamento.id == did)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        if not condominio.activo or (escritura and not depto.activo):
            denegar("El departamento o condominio se encuentra inactivo.")
        return depto, condominio

    async def cuotas(self, did: UUID, *, bloquear=False):
        query = (
            select(CuotaMantenimiento)
            .where(CuotaMantenimiento.departamento_id == did)
            .order_by(CuotaMantenimiento.id)
            .execution_options(populate_existing=True)
        )
        if bloquear:
            query = query.with_for_update()
        return list(await self.session.scalars(query))

    async def comprobante(self, id: UUID, usuario: dict, *, escritura=False, bloquear=False):
        comprobante = await self.session.get(ComprobantePago, id)
        if comprobante is None:
            raise APIError(404, "COMPROBANTE_NO_ENCONTRADO", "No existe el comprobante.")
        depto, condominio = await self.departamento(
            comprobante.departamento_id, usuario, escritura=escritura, bloquear=bloquear
        )
        return comprobante, depto, condominio

    async def auditar(self, usuario, cid, did, accion, motivo, anterior, posterior, *, exito=True):
        # El llamador mantiene el lock de condominio para no bifurcar los hashes.
        previo = await self.session.scalar(
            select(AuditoriaLogORM.hash_actual)
            .where(AuditoriaLogORM.condominio_id == cid)
            .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            .limit(1)
        )
        payload = AuditoriaPayload(
            condominio_id=str(cid),
            departamento_id=str(did),
            accion_ejecutada=accion,
            motivo=motivo,
            resultado="EXITOSO" if exito else "FALLIDO",
            actor_tipo=usuario["rol"],
            actor_id=str(usuario["sub"]),
            estado_anterior=anterior,
            estado_posterior=posterior,
            hash_previo=previo,
        )
        self.session.add(
            AuditoriaLogORM(
                condominio_id=cid,
                departamento_id=did,
                timestamp=payload.timestamp,
                accion_ejecutada=accion,
                motivo=motivo,
                resultado=payload.resultado,
                actor_tipo=payload.actor_tipo,
                actor_id=payload.actor_id,
                estado_anterior=anterior,
                estado_posterior=posterior,
                hash_previo=previo,
                hash_actual=payload.calcular_hash(),
            )
        )
        await self.session.flush()
