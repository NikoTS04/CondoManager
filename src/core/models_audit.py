"""Modelo ORM de Auditoría Inmutable (7 campos obligatorios)."""

from datetime import datetime, timezone
from typing import Any, Dict
import uuid
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base


class AuditoriaLogORM(Base):
    __tablename__ = "auditoria_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    departamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    accion_ejecutada: Mapped[str] = mapped_column(String(100), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    estado_anterior: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    estado_posterior: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    hash_actual: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_previo: Mapped[str] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "resultado IN ('EXITOSO', 'FALLIDO')", name="ck_auditoria_resultado"
        ),
    )
