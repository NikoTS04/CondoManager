"""Fondos efectivamente cobrados, separados de deuda y de crédito del residente."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class CobroMoraFondo(Base):
    __tablename__ = "cobros_mora_fondo"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    comprobante_id: Mapped[UUID] = mapped_column(ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"))
    cuota_id: Mapped[UUID] = mapped_column(ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT"))
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    edificio_id: Mapped[UUID] = mapped_column(ForeignKey("edificios.id", ondelete="RESTRICT"))
    moneda: Mapped[str] = mapped_column(Text)
    base_no_adoptada: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("comprobante_id", "cuota_id", name="uq_cobro_fondo_comprobante_cuota"),
                     CheckConstraint("base_no_adoptada >= 0", name="ck_cobro_fondo_base"),
                     CheckConstraint("moneda IN ('PEN','USD')", name="ck_cobro_fondo_moneda"),
                     Index("idx_cobro_fondo_cuota", "cuota_id"),
                     Index("idx_cobro_fondo_ambito", "condominio_id", "edificio_id", "moneda"))


class AplicacionMoras(Base):
    __tablename__ = "aplicaciones_fondo_moras"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    presupuesto_id: Mapped[UUID] = mapped_column(ForeignKey("presupuestos_mensuales.id", ondelete="RESTRICT"))
    item_id: Mapped[UUID] = mapped_column()
    edificio_id: Mapped[UUID] = mapped_column(ForeignKey("edificios.id", ondelete="RESTRICT"))
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    motivo: Mapped[str] = mapped_column(Text)
    clave_idempotencia: Mapped[str] = mapped_column(Text)
    version_solicitada: Mapped[int] = mapped_column()
    estado: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    __table_args__ = (
        UniqueConstraint("presupuesto_id", "clave_idempotencia", name="uq_aplicacion_moras_clave"),
        CheckConstraint("monto > 0 AND version_solicitada > 0", name="ck_aplicacion_moras_monto_version"),
        CheckConstraint("estado IN ('RESERVADA','CONFIRMADA','LIBERADA')", name="ck_aplicacion_moras_estado"),
        Index("idx_aplicacion_moras_edificio", "edificio_id"),
    )


class MovimientoFondoMoras(Base):
    __tablename__ = "movimientos_fondo_moras"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    edificio_id: Mapped[UUID] = mapped_column(ForeignKey("edificios.id", ondelete="RESTRICT"))
    moneda: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cobro_id: Mapped[UUID | None] = mapped_column(ForeignKey("cobros_mora_fondo.id", ondelete="RESTRICT"))
    aplicacion_id: Mapped[UUID | None] = mapped_column(ForeignKey("aplicaciones_fondo_moras.id", ondelete="RESTRICT"))
    movimiento_diario_id: Mapped[UUID | None] = mapped_column(ForeignKey("movimientos_imputacion_diaria.id", ondelete="RESTRICT"), unique=True)
    imputacion_legacy_id: Mapped[UUID | None] = mapped_column(ForeignKey("imputaciones_pago.id", ondelete="RESTRICT"), unique=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    __table_args__ = (
        UniqueConstraint("aplicacion_id", "tipo", name="uq_mov_fondo_aplicacion_tipo"),
        CheckConstraint("moneda IN ('PEN','USD')", name="ck_mov_fondo_moneda"),
        CheckConstraint("(tipo = 'COBRO' AND cobro_id IS NOT NULL AND aplicacion_id IS NULL AND importe <> 0) OR "
                        "(tipo = 'RESERVA' AND aplicacion_id IS NOT NULL AND cobro_id IS NULL AND importe < 0) OR "
                        "(tipo = 'LIBERACION' AND aplicacion_id IS NOT NULL AND cobro_id IS NULL AND importe > 0)", name="ck_mov_fondo_tipo"),
        Index("idx_mov_fondo_ambito", "condominio_id", "edificio_id", "moneda", "creado_en"),
        Index("idx_mov_fondo_cobro", "cobro_id"),
        Index("idx_mov_fondo_aplicacion", "aplicacion_id"),
    )


class EventoFondoMorasOutbox(Base):
    __tablename__ = "eventos_fondo_moras_outbox"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    edificio_id: Mapped[UUID] = mapped_column(ForeignKey("edificios.id", ondelete="RESTRICT"))
    payload: Mapped[dict] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("idx_evento_fondo_pendiente", "publicado_en", "creado_en"),
                     Index("idx_evento_fondo_edificio", "edificio_id"))
