"""Repositorio con bloqueos y savepoint dentro de la transacción de emisión."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.cuotas.saldos.exceptions import AccesoSaldoDenegadoError
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor


class SaldoFavorRepository(Protocol):
    def unidad_de_trabajo(self, condominio_id: UUID) -> AbstractAsyncContextManager[None]: ...

    async def bloquear_departamento(
        self, departamento_id: UUID, condominio_id: UUID
    ) -> Departamento | None: ...

    async def bloquear_cuota(
        self, cuota_id: UUID, departamento_id: UUID
    ) -> CuotaMantenimiento | None: ...

    async def obtener_aplicacion(self, cuota_id: UUID) -> AplicacionSaldoFavor | None: ...

    async def obtener_ultimo_hash_auditoria(self, condominio_id: UUID) -> str | None: ...

    async def guardar(
        self,
        cuota: CuotaMantenimiento,
        departamento: Departamento,
        aplicacion: AplicacionSaldoFavor,
        auditoria: AuditoriaLogORM,
    ) -> None: ...


class SQLAlchemySaldoFavorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def unidad_de_trabajo(self, condominio_id: UUID) -> AsyncIterator[None]:
        if not self._session.in_transaction():
            raise RuntimeError("La aplicación de saldo requiere la transacción externa de emisión.")
        async with self._session.begin_nested():
            # Mismo bloqueo que CON-9/CON-10: evita bifurcar la cadena del condominio.
            resultado = await self._session.execute(
                select(Condominio)
                .where(Condominio.id == condominio_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if resultado.scalar_one_or_none() is None:
                raise AccesoSaldoDenegadoError("No existe el condominio autorizado.")
            yield

    async def bloquear_departamento(
        self, departamento_id: UUID, condominio_id: UUID
    ) -> Departamento | None:
        resultado = await self._session.execute(
            select(Departamento)
            .join(Edificio, Edificio.id == Departamento.edificio_id)
            .where(
                Departamento.id == departamento_id,
                Edificio.condominio_id == condominio_id,
            )
            .with_for_update(of=Departamento)
            .execution_options(populate_existing=True)
        )
        return resultado.scalar_one_or_none()

    async def bloquear_cuota(
        self, cuota_id: UUID, departamento_id: UUID
    ) -> CuotaMantenimiento | None:
        resultado = await self._session.execute(
            select(CuotaMantenimiento)
            .where(
                CuotaMantenimiento.id == cuota_id,
                CuotaMantenimiento.departamento_id == departamento_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return resultado.scalar_one_or_none()

    async def obtener_aplicacion(self, cuota_id: UUID) -> AplicacionSaldoFavor | None:
        resultado = await self._session.execute(
            select(AplicacionSaldoFavor).where(AplicacionSaldoFavor.cuota_id == cuota_id)
        )
        return resultado.scalar_one_or_none()

    async def obtener_ultimo_hash_auditoria(self, condominio_id: UUID) -> str | None:
        resultado = await self._session.execute(
            select(AuditoriaLogORM.hash_actual)
            .where(AuditoriaLogORM.condominio_id == condominio_id)
            .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            .limit(1)
        )
        return resultado.scalar_one_or_none()

    async def guardar(
        self,
        cuota: CuotaMantenimiento,
        departamento: Departamento,
        aplicacion: AplicacionSaldoFavor,
        auditoria: AuditoriaLogORM,
    ) -> None:
        self._session.add_all([cuota, departamento, aplicacion, auditoria])
        await self._session.flush()
