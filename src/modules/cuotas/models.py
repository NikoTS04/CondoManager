"""Modelos ORM de Cuotas de Mantenimiento (Anderson - PROC-01)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class LoteCuotas(Base):
    __tablename__ = "lotes_cuotas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("presupuestos_mensuales.id", ondelete="RESTRICT"), nullable=False
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(150), nullable=False)
    total_cuotas_emitidas: Mapped[int] = mapped_column(nullable=False)
    monto_total_facturado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cuotas_cubiertas_saldo_favor: Mapped[int] = mapped_column(nullable=False)
    fecha_emision: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("condominio_id", "periodo", name="uq_lote_condominio_periodo"),
        CheckConstraint("monto_total_facturado > 0", name="ck_lote_monto"),
        CheckConstraint("total_cuotas_emitidas > 0", name="ck_lote_cantidad"),
        CheckConstraint("metodo IN ('POR_ALICUOTA', 'EQUITATIVA')", name="ck_lote_metodo"),
    )


class EventoLoteOutbox(Base):
    __tablename__ = "eventos_lote_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    lote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lotes_cuotas.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CuotaMantenimiento(Base):
    __tablename__ = "cuotas_mantenimiento"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    departamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)  # "2026-10"
    monto_ordinario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_extraordinario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    monto_mora: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    monto_descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    monto_total_exigible: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_pagado: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="EMITIDA")

    @property
    def monto_pendiente(self) -> Decimal:
        """Neto por pagar; el crédito amortizado no reduce el bruto exigible."""
        return self.monto_total_exigible - self.monto_pagado

    __table_args__ = (
        UniqueConstraint("departamento_id", "periodo", name="uq_departamento_periodo"),
        CheckConstraint("monto_ordinario >= 0.00", name="ck_cuota_monto_ordinario"),
        CheckConstraint("monto_extraordinario >= 0.00", name="ck_cuota_monto_extraordinario"),
        CheckConstraint("monto_mora >= 0.00", name="ck_cuota_monto_mora"),
        CheckConstraint("monto_descuento >= 0.00", name="ck_cuota_monto_descuento"),
        CheckConstraint("monto_total_exigible >= 0.00", name="ck_cuota_monto_total_exigible"),
        CheckConstraint(
            "monto_pagado BETWEEN 0.00 AND monto_total_exigible",
            name="ck_cuota_monto_pagado",
        ),
        CheckConstraint(
            "estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA')",
            name="ck_cuota_estado",
        ),
    )
