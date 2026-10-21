"""Modelos ORM de Áreas Comunes y Reservas (Brandon - PROC-04 / CON-41 / CON-43)."""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    # Nulo solo en reservas históricas adoptadas por CON-73.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    area_nombre: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_reserva: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    costo_reserva: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="SOLICITADA")
    # Los históricos sin marca eran UTC; las nuevas reservas conservan su zona.
    zona_horaria: Mapped[str] = mapped_column(String(40), nullable=False, default="UTC")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    fecha_cancelacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    motivo_cancelacion: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("moneda IN ('PEN', 'USD')", name="ck_reserva_moneda"),
        CheckConstraint("zona_horaria IN ('UTC', 'America/Lima')", name="ck_reserva_zona"),
        CheckConstraint("hora_fin > hora_inicio", name="ck_reserva_horario"),
        CheckConstraint("costo_reserva >= 0.00", name="ck_reserva_costo"),
        CheckConstraint(
            "estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA')",
            name="ck_reserva_estado",
        ),
        Index("idx_reservas_contexto_unidad", "condominio_id", "departamento_id"),
        Index("idx_reservas_area_fecha", "area_id", "fecha_reserva", "estado"),
    )


class BloqueoArea(Base):
    __tablename__ = "bloqueos_area"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("areas_comunes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (CheckConstraint("fin > inicio", name="ck_bloqueo_intervalo"),)


class CobroReserva(Base):
    """Vínculo financiero explícito; una tarifa o un voucher en revisión no son cobros.

    Su productor es el flujo financiero integrado. CON-46 solo consulta estos
    registros y nunca acredita dinero ni crea comprobantes aprobados.
    """

    __tablename__ = "cobros_reserva"

    reserva_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reservas.id", ondelete="RESTRICT"), primary_key=True
    )
    comprobante_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_compensado: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    reembolsable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_cobro_reserva_monto"),
        CheckConstraint(
            "monto_compensado >= 0 AND monto_compensado <= monto",
            name="ck_cobro_reserva_compensado",
        ),
    )


class CancelacionReserva(Base):
    """Resultado original y solicitud de ajuste: una sola por reserva."""

    __tablename__ = "cancelaciones_reserva"

    reserva_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reservas.id", ondelete="RESTRICT"), primary_key=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    motivo: Mapped[str] = mapped_column(String(500), nullable=False)
    fecha_cancelacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resultado: Mapped[dict] = mapped_column(JSONB, nullable=False)


class EventoReservaOutbox(Base):
    __tablename__ = "eventos_reserva_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    reserva_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reservas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        default="ReservaCanceladaEvent",
        server_default="ReservaCanceladaEvent",
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("reserva_id", "tipo", name="uq_evento_reserva_tipo"),
        Index("idx_evento_reserva_pendiente", "publicado_en", "creado_en"),
    )
