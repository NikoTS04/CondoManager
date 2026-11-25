"""Persistencia del reporte original y su evidencia privada."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Incidencia(Base):
    __tablename__ = "incidencias"
    __table_args__ = (
        UniqueConstraint(
            "condominio_id", "reportante_id", "clave_idempotencia", name="uq_incidencia_operacion"
        ),
        CheckConstraint("version >= 1", name="ck_incidencia_version"),
        CheckConstraint(
            "(categoria_confirmada IS NULL) = (prioridad IS NULL)",
            name="ck_incidencia_clasificacion",
        ),
        CheckConstraint(
            "prioridad IN ('BAJA', 'MEDIA', 'ALTA', 'URGENTE')", name="ck_incidencia_prioridad"
        ),
        CheckConstraint(
            "(estado = 'RECHAZADO') = (motivo_rechazo IS NOT NULL)",
            name="ck_incidencia_motivo_rechazo",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    reportante_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True
    )
    departamento_id: Mapped[UUID] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), index=True
    )
    clave_idempotencia: Mapped[UUID]
    hash_solicitud: Mapped[str] = mapped_column(Text)
    ubicacion: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    urgencia: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="REGISTRADO")
    categoria_confirmada: Mapped[str | None] = mapped_column(Text)
    prioridad: Mapped[str | None] = mapped_column(Text)
    motivo_rechazo: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default="1")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    evidencia: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    evidencia_mime: Mapped[str | None] = mapped_column(Text)

    @property
    def tiene_evidencia(self) -> bool:
        return self.evidencia_mime is not None
