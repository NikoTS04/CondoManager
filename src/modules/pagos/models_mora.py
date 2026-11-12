"""Ledger prospectivo inmutable de devengos, compensaciones y cobros por componente."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class DevengoMora(Base):
    __tablename__ = "devengos_mora"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cuota_id: Mapped[UUID] = mapped_column(
        ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT")
    )
    fecha_local: Mapped[date] = mapped_column(Date)
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    politica: Mapped[dict] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    __table_args__ = (
        UniqueConstraint("cuota_id", "fecha_local", name="uq_devengo_cuota_fecha"),
        CheckConstraint("importe > 0", name="ck_devengo_importe"),
    )


class ConciliacionDiaria(Base):
    __tablename__ = "conciliaciones_diarias"
    comprobante_id: Mapped[UUID] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"), primary_key=True
    )
    cuotas_evaluadas: Mapped[list] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AjusteDevengoMora(Base):
    __tablename__ = "ajustes_devengo_mora"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    devengo_id: Mapped[UUID] = mapped_column(ForeignKey("devengos_mora.id", ondelete="RESTRICT"))
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    comprobante_causante_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    __table_args__ = (
        CheckConstraint("importe <> 0", name="ck_ajuste_devengo_importe"),
        Index("idx_ajuste_devengo", "devengo_id"),
    )


class MovimientoImputacionDiaria(Base):
    __tablename__ = "movimientos_imputacion_diaria"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    comprobante_id: Mapped[UUID] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT")
    )
    cuota_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT")
    )
    componente: Mapped[str] = mapped_column(String(20))
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    comprobante_causante_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    __table_args__ = (
        CheckConstraint("importe <> 0", name="ck_mov_diario_importe"),
        CheckConstraint(
            "componente IN ('MORA','EXTRAORDINARIA','ORDINARIA','CREDITO')",
            name="ck_mov_diario_componente",
        ),
        CheckConstraint(
            "(componente = 'CREDITO') = (cuota_id IS NULL)", name="ck_mov_diario_destino"
        ),
        Index("idx_mov_diario_comprobante", "comprobante_id"),
        Index("idx_mov_diario_cuota", "cuota_id"),
    )


class EventoMoraOutbox(Base):
    __tablename__ = "eventos_mora_outbox"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    cuota_id: Mapped[UUID] = mapped_column(
        ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT")
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("idx_evento_mora_pendiente", "publicado_en", "creado_en"),)
