"""Extensiones aditivas de CON-70, sin modificar tablas de otros dominios."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ArchivoVoucher(Base):
    __tablename__ = "archivos_voucher"

    nombre: Mapped[str] = mapped_column(Text, primary_key=True)
    departamento_id: Mapped[UUID] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_id: Mapped[UUID] = mapped_column(nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    comprobante_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("size_bytes BETWEEN 1 AND 5242880", name="ck_voucher_size"),
        CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'application/pdf')",
            name="ck_voucher_content_type",
        ),
        Index("idx_voucher_pendientes", "comprobante_id", "creado_en"),
    )


class RevisionPago(Base):
    __tablename__ = "revisiones_pago"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    comprobante_id: Mapped[UUID] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    resultado: Mapped[dict] = mapped_column(JSONB, nullable=False)
    archivo_nombre: Mapped[str | None] = mapped_column(
        ForeignKey("archivos_voucher.nombre", ondelete="RESTRICT"), nullable=True
    )
    notas_internas: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('APROBADO', 'OBSERVADO', 'RECHAZADO')", name="ck_revision_decision"
        ),
        Index("idx_revision_comprobante_fecha", "comprobante_id", "creado_en"),
    )


class EventoPagoOutbox(Base):
    __tablename__ = "eventos_pago_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    comprobante_id: Mapped[UUID] = mapped_column(
        ForeignKey("comprobantes_pago.id", ondelete="RESTRICT"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("idx_evento_pago_pendiente", "publicado_en", "creado_en"),)
