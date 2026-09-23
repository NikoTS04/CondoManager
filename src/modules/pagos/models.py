"""Modelos ORM de Pagos y Conciliación (Tarqui - PROC-02)."""

from datetime import date, datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class ComprobantePago(Base):
    __tablename__ = "comprobantes_pago"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    departamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    banco_origen: Mapped[str] = mapped_column(String(30), nullable=False)
    numero_operacion: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_operacion: Mapped[date] = mapped_column(Date, nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    url_voucher: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="EN_REVISION"
    )
    motivo_rechazo: Mapped[str] = mapped_column(Text, nullable=True)
    conciliado_por: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    conciliado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("monto > 0.00", name="ck_comprobante_monto"),
        CheckConstraint(
            "estado IN ('EN_REVISION', 'APROBADO', 'RECHAZADO', 'OBSERVADO')",
            name="ck_comprobante_estado",
        ),
    )


class ImputacionPago(Base):
    __tablename__ = "imputaciones_pago"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    comprobante_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cuota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT"),
        nullable=False,
    )
    monto_aplicado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_imputacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("monto_aplicado > 0.00", name="ck_imputacion_monto"),
    )
