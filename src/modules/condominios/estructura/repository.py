"""Persistencia contextual; el condominio serializa padrón y cadena de auditoría."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio


class EstructuraRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def contexto(self, condominio_id: UUID, escritura=False):
        consulta = select(Condominio).where(
            Condominio.id == condominio_id, Condominio.activo.is_(True)
        )
        if escritura:
            consulta = consulta.with_for_update()
        return (await self.session.execute(consulta)).scalar_one_or_none()

    async def edificios(self, condominio_id: UUID):
        resultado = await self.session.execute(
            select(Edificio)
            .where(Edificio.condominio_id == condominio_id)
            .order_by(Edificio.nombre_bloque, Edificio.id)
        )
        return list(resultado.scalars())

    async def edificio(self, condominio_id: UUID, edificio_id: UUID):
        return (
            await self.session.execute(
                select(Edificio).where(
                    Edificio.condominio_id == condominio_id, Edificio.id == edificio_id
                )
            )
        ).scalar_one_or_none()

    async def departamentos(self, condominio_id: UUID, edificio_id=None, activo=None):
        consulta = (
            select(Departamento).join(Edificio).where(Edificio.condominio_id == condominio_id)
        )
        if edificio_id is not None:
            consulta = consulta.where(Departamento.edificio_id == edificio_id)
        if activo is not None:
            consulta = consulta.where(Departamento.activo.is_(activo))
        return list(
            (
                await self.session.execute(
                    consulta.order_by(
                        Departamento.edificio_id, Departamento.piso, Departamento.numero
                    )
                )
            ).scalars()
        )

    async def departamento(self, condominio_id: UUID, departamento_id: UUID):
        return (
            await self.session.execute(
                select(Departamento)
                .join(Edificio)
                .where(Edificio.condominio_id == condominio_id, Departamento.id == departamento_id)
            )
        ).scalar_one_or_none()

    async def ultimo_hash(self, condominio_id):
        return (
            await self.session.execute(
                select(AuditoriaLogORM.hash_actual)
                .where(AuditoriaLogORM.condominio_id == condominio_id)
                .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def guardar(self, recurso, auditoria):
        async with self.session.begin_nested():
            self.session.add(recurso)
            await self.session.flush()
            self.session.add(auditoria)
            await self.session.flush()
        return recurso
