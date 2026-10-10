"""Modelo ORM del presupuesto mensual ordinario de CON-9."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class PresupuestoMensual(Base):
    __tablename__ = "presupuestos_mensuales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    monto_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="BORRADOR")
    creado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    aprobado_por: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aprobado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "condominio_id",
            "periodo",
            name="uq_presupuesto_condominio_periodo",
        ),
        CheckConstraint(
            "periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
            name="ck_presupuesto_periodo",
        ),
        CheckConstraint("moneda IN ('PEN', 'USD')", name="ck_presupuesto_moneda"),
        CheckConstraint("monto_total > 0.00", name="ck_presupuesto_monto_positivo"),
        CheckConstraint(
            "CASE "
            "WHEN periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN "
            "EXTRACT(YEAR FROM fecha_vencimiento) = "
            "CAST(SUBSTRING(periodo FROM 1 FOR 4) AS INTEGER) "
            "AND EXTRACT(MONTH FROM fecha_vencimiento) = "
            "CAST(SUBSTRING(periodo FROM 6 FOR 2) AS INTEGER) "
            "ELSE FALSE END",
            name="ck_presupuesto_vencimiento_periodo",
        ),
        CheckConstraint(
            "(estado = 'BORRADOR' AND aprobado_por IS NULL AND aprobado_en IS NULL) "
            "OR (estado = 'APROBADO' AND aprobado_por IS NOT NULL "
            "AND aprobado_en IS NOT NULL)",
            name="ck_presupuesto_aprobacion",
        ),
        CheckConstraint(
            "estado IN ('BORRADOR', 'APROBADO')",
            name="ck_presupuesto_estado",
        ),
        Index(
            "idx_presupuestos_condominio_estado",
            "condominio_id",
            "estado",
        ),
    )
