"""Evidencia persistente e idempotente de la amortización inicial."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class AplicacionSaldoFavor(Base):
    __tablename__ = "aplicaciones_saldo_favor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cuotas_mantenimiento.id", ondelete="RESTRICT"),
        nullable=False,
    )
    saldo_previo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_aplicado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_pendiente: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saldo_restante: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado_anterior: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_posterior: Mapped[str] = mapped_column(String(20), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint("cuota_id", name="uq_aplicacion_saldo_cuota"),
        CheckConstraint(
            "saldo_previo >= 0 AND monto_aplicado >= 0 AND monto_pendiente >= 0 "
            "AND saldo_restante >= 0 AND saldo_previo = monto_aplicado + saldo_restante",
            name="ck_aplicacion_saldo_importes",
        ),
        CheckConstraint(
            "estado_anterior = 'EMITIDA' AND "
            "((estado_posterior = 'PAGADA' AND monto_pendiente = 0) OR "
            "(estado_posterior = 'PENDIENTE' AND monto_pendiente > 0))",
            name="ck_aplicacion_saldo_estados",
        ),
    )
