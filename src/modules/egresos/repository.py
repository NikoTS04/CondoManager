"""Consultas SQLAlchemy asíncronas para el agregado de egresos.

El repositorio nunca confirma transacciones: el servicio dueño de la unidad de
trabajo debe incluir mutaciones, ledger y auditoría en una sola transacción SQL.
"""

from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.condominios.models import Condominio
from src.modules.cuotas.presupuestos.models import ConceptoPresupuestal, PresupuestoMensual
from src.modules.egresos.models import (
    AperturaCaja,
    AprobacionEgreso,
    ConfiguracionAprobacionEgreso,
    CuentaCaja,
    DocumentoFinanciero,
    Egreso,
    HistorialEgreso,
    MovimientoCaja,
    PagoEgreso,
    ReversoPago,
)


class SQLAlchemyEgresosRepository:
    """Capa de acceso a datos, sin política de negocio ni commits propios."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bloquear_condominio(self, condominio_id: UUID) -> Condominio | None:
        query = (
            select(Condominio)
            .where(Condominio.id == condominio_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(query)

    async def obtener_condominio(self, condominio_id: UUID) -> Condominio | None:
        return await self.session.get(Condominio, condominio_id)

    async def obtener_concepto(
        self, condominio_id: UUID, concepto_id: UUID
    ) -> ConceptoPresupuestal | None:
        query = select(ConceptoPresupuestal).where(
            ConceptoPresupuestal.condominio_id == condominio_id,
            ConceptoPresupuestal.id == concepto_id,
            ConceptoPresupuestal.activo.is_(True),
        )
        return await self.session.scalar(query)

    async def obtener_presupuesto(
        self, condominio_id: UUID, presupuesto_id: UUID
    ) -> PresupuestoMensual | None:
        query = select(PresupuestoMensual).where(
            PresupuestoMensual.condominio_id == condominio_id,
            PresupuestoMensual.id == presupuesto_id,
        )
        return await self.session.scalar(query)

    async def obtener_egreso(
        self, condominio_id: UUID, egreso_id: UUID, *, bloquear: bool = False
    ) -> Egreso | None:
        query = (
            select(Egreso)
            .where(
                Egreso.condominio_id == condominio_id,
                Egreso.id == egreso_id,
            )
            .options(
                selectinload(Egreso.concepto),
                selectinload(Egreso.documentos),
                selectinload(Egreso.aprobaciones),
                selectinload(Egreso.pagos).selectinload(PagoEgreso.movimientos),
            )
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query.execution_options(populate_existing=True))

    async def listar_egresos(
        self,
        condominio_id: UUID,
        *,
        fecha_desde=None,
        fecha_hasta=None,
        estado: str | None = None,
        proveedor_id: UUID | None = None,
        concepto_id: UUID | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[Sequence[Egreso], bool]:
        query = (
            select(Egreso)
            .where(Egreso.condominio_id == condominio_id)
            .options(
                selectinload(Egreso.concepto),
                selectinload(Egreso.documentos),
                selectinload(Egreso.aprobaciones),
                selectinload(Egreso.pagos).selectinload(PagoEgreso.movimientos),
            )
        )
        if fecha_desde is not None:
            query = query.where(Egreso.fecha_gasto >= fecha_desde)
        if fecha_hasta is not None:
            query = query.where(Egreso.fecha_gasto <= fecha_hasta)
        if estado is not None:
            query = query.where(Egreso.estado == estado)
        if proveedor_id is not None:
            query = query.where(Egreso.proveedor_id == proveedor_id)
        if concepto_id is not None:
            query = query.where(Egreso.concepto_id == concepto_id)
        query = query.order_by(Egreso.fecha_gasto.desc(), Egreso.id).offset(offset).limit(limit + 1)
        rows = list((await self.session.scalars(query)).all())
        return rows[:limit], len(rows) > limit

    async def agregar_egreso(self, egreso: Egreso) -> Egreso:
        self.session.add(egreso)
        await self.session.flush()
        return egreso

    async def configuracion_aprobacion(
        self, condominio_id: UUID, *, bloquear: bool = False
    ) -> ConfiguracionAprobacionEgreso | None:
        query = select(ConfiguracionAprobacionEgreso).where(
            ConfiguracionAprobacionEgreso.condominio_id == condominio_id
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query.execution_options(populate_existing=True))

    async def guardar_configuracion(
        self, configuracion: ConfiguracionAprobacionEgreso
    ) -> ConfiguracionAprobacionEgreso:
        self.session.add(configuracion)
        await self.session.flush()
        return configuracion

    async def agregar_aprobacion(self, aprobacion: AprobacionEgreso) -> AprobacionEgreso:
        self.session.add(aprobacion)
        await self.session.flush()
        return aprobacion

    async def agregar_historial(self, entrada: HistorialEgreso) -> HistorialEgreso:
        self.session.add(entrada)
        await self.session.flush()
        return entrada

    async def historial_egreso(
        self, condominio_id: UUID, egreso_id: UUID
    ) -> Sequence[HistorialEgreso]:
        query = (
            select(HistorialEgreso)
            .where(
                HistorialEgreso.condominio_id == condominio_id,
                HistorialEgreso.egreso_id == egreso_id,
            )
            .order_by(HistorialEgreso.creado_en, HistorialEgreso.id)
        )
        return (await self.session.scalars(query)).all()

    async def aprobaciones_egreso(
        self, condominio_id: UUID, egreso_id: UUID
    ) -> Sequence[AprobacionEgreso]:
        query = (
            select(AprobacionEgreso)
            .where(
                AprobacionEgreso.condominio_id == condominio_id,
                AprobacionEgreso.egreso_id == egreso_id,
            )
            .order_by(AprobacionEgreso.creado_en, AprobacionEgreso.id)
        )
        return (await self.session.scalars(query)).all()

    async def agregar_documento(self, documento: DocumentoFinanciero) -> DocumentoFinanciero:
        self.session.add(documento)
        await self.session.flush()
        return documento

    async def obtener_documento(
        self, condominio_id: UUID, documento_id: UUID, *, egreso_id: UUID | None = None
    ) -> DocumentoFinanciero | None:
        query = select(DocumentoFinanciero).where(
            DocumentoFinanciero.condominio_id == condominio_id,
            DocumentoFinanciero.id == documento_id,
        )
        if egreso_id is not None:
            query = query.where(DocumentoFinanciero.egreso_id == egreso_id)
        return await self.session.scalar(query)

    async def obtener_pago_por_idempotencia(
        self, condominio_id: UUID, scope: str, key: str
    ) -> PagoEgreso | None:
        query = select(PagoEgreso).where(
            PagoEgreso.condominio_id == condominio_id,
            PagoEgreso.idempotency_scope == scope,
            PagoEgreso.idempotency_key == key,
        )
        return await self.session.scalar(query)

    async def agregar_pago(self, pago: PagoEgreso) -> PagoEgreso:
        self.session.add(pago)
        await self.session.flush()
        return pago

    async def listar_pagos_egreso(
        self, condominio_id: UUID, egreso_id: UUID
    ) -> Sequence[PagoEgreso]:
        query = (
            select(PagoEgreso)
            .where(
                PagoEgreso.condominio_id == condominio_id,
                PagoEgreso.egreso_id == egreso_id,
            )
            .order_by(PagoEgreso.creado_en, PagoEgreso.id)
        )
        return (await self.session.scalars(query)).all()

    async def agregar_reverso(self, reverso: ReversoPago) -> ReversoPago:
        self.session.add(reverso)
        await self.session.flush()
        return reverso

    async def obtener_reverso_por_idempotencia(
        self, condominio_id: UUID, key: str
    ) -> ReversoPago | None:
        query = select(ReversoPago).where(
            ReversoPago.condominio_id == condominio_id,
            ReversoPago.idempotency_key == key,
        )
        return await self.session.scalar(query)

    async def obtener_reverso_por_pago(
        self, condominio_id: UUID, pago_id: UUID, *, bloquear: bool = False
    ) -> ReversoPago | None:
        query = select(ReversoPago).where(
            ReversoPago.condominio_id == condominio_id,
            ReversoPago.pago_id == pago_id,
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query.execution_options(populate_existing=True))

    async def obtener_cuenta(
        self, condominio_id: UUID, cuenta_id: UUID, *, bloquear: bool = False
    ) -> CuentaCaja | None:
        query = select(CuentaCaja).where(
            CuentaCaja.condominio_id == condominio_id,
            CuentaCaja.id == cuenta_id,
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query.execution_options(populate_existing=True))

    async def obtener_apertura(
        self, condominio_id: UUID, cuenta_id: UUID, *, bloquear: bool = False
    ) -> AperturaCaja | None:
        query = select(AperturaCaja).where(
            AperturaCaja.condominio_id == condominio_id,
            AperturaCaja.cuenta_id == cuenta_id,
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query.execution_options(populate_existing=True))

    async def obtener_apertura_por_idempotencia(
        self, condominio_id: UUID, key: str
    ) -> AperturaCaja | None:
        query = select(AperturaCaja).where(
            AperturaCaja.condominio_id == condominio_id,
            AperturaCaja.idempotency_key == key,
        )
        return await self.session.scalar(query)

    async def agregar_apertura(self, apertura: AperturaCaja) -> AperturaCaja:
        self.session.add(apertura)
        await self.session.flush()
        return apertura

    async def listar_cuentas_caja(self, condominio_id: UUID) -> Sequence[CuentaCaja]:
        query = (
            select(CuentaCaja)
            .where(CuentaCaja.condominio_id == condominio_id)
            .order_by(CuentaCaja.moneda, CuentaCaja.cuenta_referencia, CuentaCaja.id)
        )
        return (await self.session.scalars(query)).all()

    async def saldo_caja(self, condominio_id: UUID, cuenta_id: UUID) -> Decimal:
        query = select(
            func.coalesce(
                func.sum(MovimientoCaja.importe),
                literal(Decimal("0.00")),
            )
        ).where(
            MovimientoCaja.condominio_id == condominio_id,
            MovimientoCaja.cuenta_id == cuenta_id,
        )
        saldo = await self.session.scalar(query)
        return Decimal(saldo or Decimal("0.00"))

    async def movimientos_caja(
        self, condominio_id: UUID, cuenta_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> Sequence[MovimientoCaja]:
        query = (
            select(MovimientoCaja)
            .where(
                MovimientoCaja.condominio_id == condominio_id,
                MovimientoCaja.cuenta_id == cuenta_id,
            )
            .order_by(MovimientoCaja.reconocido_en.desc(), MovimientoCaja.id)
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.scalars(query)).all()

    async def agregar_movimiento(self, movimiento: MovimientoCaja) -> MovimientoCaja:
        self.session.add(movimiento)
        await self.session.flush()
        return movimiento
