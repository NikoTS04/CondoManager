"""Área común y condiciones de uso compatibles con el esquema histórico."""

import uuid
from datetime import time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class AreaComun(Base):
    __tablename__ = "areas_comunes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("condominios.id", ondelete="CASCADE"), nullable=False
    )
    edificio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("edificios.id", ondelete="SET NULL"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    aforo_maximo: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_reserva: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    tiempo_maximo_horas: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4, server_default=text("4")
    )
    esta_activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    hora_apertura: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(0), server_default=text("'00:00'")
    )
    hora_cierre: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(23, 59), server_default=text("'23:59'")
    )

    __table_args__ = (
        CheckConstraint("aforo_maximo > 0", name="ck_area_aforo"),
        CheckConstraint("costo_reserva >= 0.00", name="ck_area_costo"),
        CheckConstraint("tiempo_maximo_horas >= 1", name="ck_area_tiempo_maximo"),
        CheckConstraint(
            "hora_cierre > hora_apertura AND EXTRACT(SECOND FROM hora_apertura) = 0 AND EXTRACT(SECOND FROM hora_cierre) = 0",
            name="ck_area_horario_catalogo",
        ),
        Index("idx_areas_catalogo_contexto", "condominio_id", "esta_activa", "nombre"),
    )
