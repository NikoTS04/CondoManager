"""Modelos ORM de Áreas Comunes y Reservas (Brandon - PROC-04)."""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.modules.reservas.areas.models import AreaComun as AreaComun


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas_comunes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    departamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fecha_reserva: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    costo_reserva: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="SOLICITADA")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="ck_reserva_horario"),
        CheckConstraint("costo_reserva >= 0.00", name="ck_reserva_costo"),
        CheckConstraint(
            "estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA')",
            name="ck_reserva_estado",
        ),
    )
