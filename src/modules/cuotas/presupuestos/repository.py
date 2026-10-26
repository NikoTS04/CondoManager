"""Persistencia SQLAlchemy del presupuesto mensual de CON-9."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.presupuestos.exceptions import PresupuestoPeriodoDuplicadoError
from src.modules.cuotas.presupuestos.models import ConceptoPresupuestal, PresupuestoMensual
from src.modules.cuotas.prorrateo import calcular_prorrateo
from src.modules.cuotas.prorrateo_schemas import ItemPresupuesto


class PresupuestoRepository(Protocol):
    async def preparar_detalle(self, condominio_id: UUID, items: list) -> dict: ...
    async def obtener_condominio(self, condominio_id: UUID) -> Condominio | None: ...

    async def obtener_por_id(
        self,
        presupuesto_id: UUID,
        condominio_id: UUID | None,
        *,
        bloquear: bool,
    ) -> PresupuestoMensual | None: ...

    async def obtener_por_condominio_periodo(
        self, condominio_id: UUID, periodo: str
    ) -> PresupuestoMensual | None: ...

    async def obtener_aprobado_por_periodo(
        self, condominio_id: UUID, periodo: str
    ) -> PresupuestoMensual | None: ...

    async def obtener_ultimo_hash_auditoria(self, condominio_id: UUID) -> str | None: ...

    async def agregar(
        self,
        presupuesto: PresupuestoMensual,
        auditoria: AuditoriaLogORM,
    ) -> PresupuestoMensual: ...

    async def guardar_cambio(
        self,
        presupuesto: PresupuestoMensual,
        auditoria: AuditoriaLogORM,
    ) -> PresupuestoMensual: ...


class SQLAlchemyPresupuestoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener_condominio(self, condominio_id: UUID) -> Condominio | None:
        resultado = await self._session.execute(
            select(Condominio).where(Condominio.id == condominio_id).with_for_update()
        )
        return resultado.scalar_one_or_none()

    async def obtener_por_id(
        self,
        presupuesto_id: UUID,
        condominio_id: UUID | None,
        *,
        bloquear: bool,
    ) -> PresupuestoMensual | None:
        consulta = select(PresupuestoMensual).where(PresupuestoMensual.id == presupuesto_id)
        if condominio_id is not None:
            consulta = consulta.where(PresupuestoMensual.condominio_id == condominio_id)
        if bloquear:
            cid = await self._session.scalar(select(PresupuestoMensual.condominio_id).where(
                PresupuestoMensual.id == presupuesto_id,
                *([PresupuestoMensual.condominio_id == condominio_id] if condominio_id is not None else []),
            ))
            if cid is None:
                return None
            await self.obtener_condominio(cid)
            consulta = consulta.with_for_update()
        resultado = await self._session.execute(consulta.execution_options(populate_existing=True))
        return resultado.scalar_one_or_none()

    async def preparar_detalle(self, condominio_id, items):
        edificios = list(await self._session.scalars(select(Edificio).where(Edificio.condominio_id == condominio_id).order_by(Edificio.id)))
        departamentos = list(await self._session.scalars(
            select(Departamento).join(Edificio).where(Edificio.condominio_id == condominio_id, Departamento.activo.is_(True)).order_by(Departamento.id)
        ))
        conceptos = list(await self._session.scalars(select(ConceptoPresupuestal).where(ConceptoPresupuestal.condominio_id == condominio_id)))
        return calcular_prorrateo([ItemPresupuesto.model_validate(i) for i in items], edificios, departamentos, {c.id: c for c in conceptos})

    async def obtener_por_condominio_periodo(
        self, condominio_id: UUID, periodo: str
    ) -> PresupuestoMensual | None:
        resultado = await self._session.execute(
            select(PresupuestoMensual).where(
                PresupuestoMensual.condominio_id == condominio_id,
                PresupuestoMensual.periodo == periodo,
            )
        )
        return resultado.scalar_one_or_none()

    async def obtener_aprobado_por_periodo(
        self, condominio_id: UUID, periodo: str
    ) -> PresupuestoMensual | None:
        resultado = await self._session.execute(
            select(PresupuestoMensual).where(
                PresupuestoMensual.condominio_id == condominio_id,
                PresupuestoMensual.periodo == periodo,
                PresupuestoMensual.estado == "APROBADO",
            )
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

    async def agregar(
        self,
        presupuesto: PresupuestoMensual,
        auditoria: AuditoriaLogORM,
    ) -> PresupuestoMensual:
        self._session.add(presupuesto)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise PresupuestoPeriodoDuplicadoError(
                "Ya existe un presupuesto para el condominio y periodo indicados."
            ) from exc
        self._session.add(auditoria)
        await self._session.flush()
        return presupuesto

    async def guardar_cambio(
        self,
        presupuesto: PresupuestoMensual,
        auditoria: AuditoriaLogORM,
    ) -> PresupuestoMensual:
        self._session.add(presupuesto)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise PresupuestoPeriodoDuplicadoError(
                "Ya existe un presupuesto para el condominio y periodo indicados."
            ) from exc
        self._session.add(auditoria)
        await self._session.flush()
        return presupuesto
