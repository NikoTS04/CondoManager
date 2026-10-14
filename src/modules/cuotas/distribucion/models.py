"""Configuración vigente, única por condominio."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ConfiguracionDistribucion(Base):
    __tablename__ = "configuraciones_distribucion"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    actualizado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("condominio_id", name="uq_distribucion_condominio"),
        CheckConstraint("metodo IN ('POR_ALICUOTA', 'EQUITATIVA')", name="ck_distribucion_metodo"),
    )
