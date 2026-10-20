"""Contrato de persistencia y adaptación SQLAlchemy para CON-10."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion


@dataclass(frozen=True)
class DepartamentoDistribucion:
    id: UUID
    coeficiente: Decimal


class DistribucionRepository(Protocol):
    async def obtener_condominio(
        self, condominio_id: UUID, *, bloquear: bool = False
    ) -> Condominio | None: ...

    async def obtener_configuracion(
        self, condominio_id: UUID
    ) -> ConfiguracionDistribucion | None: ...

    async def listar_departamentos_para_distribucion(
        self, condominio_id: UUID
    ) -> list[DepartamentoDistribucion]: ...

    async def obtener_ultimo_hash_auditoria(self, condominio_id: UUID) -> str | None: ...

    async def guardar_cambio(
        self, configuracion: ConfiguracionDistribucion, auditoria: AuditoriaLogORM
    ) -> ConfiguracionDistribucion: ...


class SQLAlchemyDistribucionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener_condominio(
        self, condominio_id: UUID, *, bloquear: bool = False
    ) -> Condominio | None:
        consulta = select(Condominio).where(Condominio.id == condominio_id)
        if bloquear:
            # Bloquear la raíz serializa incluso dos PUT de creación sin fila previa.
            consulta = consulta.with_for_update()
        resultado = await self._session.execute(consulta)
        return resultado.scalar_one_or_none()

    async def obtener_configuracion(self, condominio_id: UUID) -> ConfiguracionDistribucion | None:
        resultado = await self._session.execute(
            select(ConfiguracionDistribucion).where(
                ConfiguracionDistribucion.condominio_id == condominio_id
            )
        )
        return resultado.scalar_one_or_none()

    async def listar_departamentos_para_distribucion(
        self, condominio_id: UUID
    ) -> list[DepartamentoDistribucion]:
        """Padrón persistente activo de todas las torres del condominio (CON-3)."""
        resultado = await self._session.execute(
            select(Departamento.id, Departamento.coeficiente_participacion)
            .join(Edificio, Edificio.id == Departamento.edificio_id)
            .where(Edificio.condominio_id == condominio_id, Departamento.activo.is_(True))
            .order_by(Departamento.id)
        )
        return [DepartamentoDistribucion(id=fila[0], coeficiente=fila[1]) for fila in resultado]

    async def obtener_ultimo_hash_auditoria(self, condominio_id: UUID) -> str | None:
        resultado = await self._session.execute(
            select(AuditoriaLogORM.hash_actual)
            .where(AuditoriaLogORM.condominio_id == condominio_id)
            .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            .limit(1)
        )
        return resultado.scalar_one_or_none()

    async def guardar_cambio(
        self, configuracion: ConfiguracionDistribucion, auditoria: AuditoriaLogORM
    ) -> ConfiguracionDistribucion:
        self._session.add_all([configuracion, auditoria])
        await self._session.flush()
        return configuracion
