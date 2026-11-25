"""Avisos de vencimiento de contrato (CON-50).

`contrato_id` no tiene llave foránea: la tabla de contratos (CON-49) aún no existe.
CON-49 puede añadirla cuando exista, sin cambiar esta tabla.
"""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class AvisoContrato(Base):
    __tablename__ = "avisos_contrato"
    __table_args__ = (
        UniqueConstraint("contrato_id", "vigencia", "umbral_dias", name="uq_aviso_contrato_umbral"),
        CheckConstraint("umbral_dias IN (60, 30)", name="ck_aviso_contrato_umbral"),
        CheckConstraint("estado IN ('GENERADO', 'OMITIDO')", name="ck_aviso_contrato_estado"),
        CheckConstraint(
            "prioridad IN ('INFORMATIVA', 'PRIORITARIA')", name="ck_aviso_contrato_prioridad"
        ),
        CheckConstraint(
            "(estado = 'OMITIDO') = (omitido_por_umbral IS NOT NULL)",
            name="ck_aviso_contrato_omision",
        ),
        CheckConstraint("dias_restantes >= 0", name="ck_aviso_contrato_dias"),
        Index("ix_aviso_contrato_condominio", "condominio_id", "creado_en"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    contrato_id: Mapped[UUID]
    vigencia: Mapped[str] = mapped_column(Text)
    umbral_dias: Mapped[int]
    estado: Mapped[str] = mapped_column(Text)
    prioridad: Mapped[str] = mapped_column(Text)
    destinatario_rol: Mapped[str] = mapped_column(Text, default="ADMIN_JUNTA")
    fecha_fin: Mapped[date] = mapped_column(Date)
    dias_restantes: Mapped[int]
    motivo: Mapped[str] = mapped_column(Text)
    omitido_por_umbral: Mapped[int | None]
    fecha_evaluacion: Mapped[date] = mapped_column(Date)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
