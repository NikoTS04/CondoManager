"""Modelos ORM de Cuotas de Mantenimiento (Anderson - PROC-01)."""

from datetime import date
from decimal import Decimal
import uuid
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class CuotaMantenimiento(Base):
    __tablename__ = "cuotas_mantenimiento"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
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
    monto_total_exigible: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    monto_pagado: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="EMITIDA"
    )

    __table_args__ = (
        UniqueConstraint("departamento_id", "periodo", name="uq_departamento_periodo"),
        CheckConstraint("monto_ordinario >= 0.00", name="ck_cuota_monto_ordinario"),
        CheckConstraint(
            "monto_extraordinario >= 0.00", name="ck_cuota_monto_extraordinario"
        ),
        CheckConstraint("monto_mora >= 0.00", name="ck_cuota_monto_mora"),
        CheckConstraint("monto_descuento >= 0.00", name="ck_cuota_monto_descuento"),
        CheckConstraint(
            "monto_total_exigible >= 0.00", name="ck_cuota_monto_total_exigible"
        ),
        CheckConstraint(
            "monto_pagado BETWEEN 0.00 AND monto_total_exigible",
            name="ck_cuota_monto_pagado",
        ),
        CheckConstraint(
            "estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA')",
            name="ck_cuota_estado",
        ),
    )
