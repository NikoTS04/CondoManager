"""Persistencia del reporte original y su evidencia privada."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    Numeric,
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
        CheckConstraint(
            "estado IN ('REGISTRADO','RECHAZADO','ASIGNADO','EN_PROCESO','RESUELTO','CERRADO')",
            name="ck_incidencia_estado",
        ),
        CheckConstraint(
            "NOT (responsable_usuario_id IS NOT NULL AND responsable_proveedor_id IS NOT NULL)",
            name="ck_incidencia_responsable",
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
    asignacion_actual_id: Mapped[UUID | None] = mapped_column(nullable=True)
    responsable_usuario_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    responsable_proveedor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    proveedor_nombre: Mapped[str | None] = mapped_column(Text)
    correo_proveedor: Mapped[str | None] = mapped_column(Text)
    fecha_asignacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plazo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def tiene_evidencia(self) -> bool:
        return self.evidencia_mime is not None


class AsignacionIncidencia(Base):
    """Asignación confirmada por Junta: una fila por clave de idempotencia."""

    __tablename__ = "incidencias_asignaciones"
    __table_args__ = (
        UniqueConstraint(
            "condominio_id", "incidencia_id", "clave_idempotencia", name="uq_asignacion_operacion"
        ),
        CheckConstraint(
            "NOT (responsable_usuario_id IS NOT NULL AND responsable_proveedor_id IS NOT NULL)",
            name="ck_asignacion_responsable",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    incidencia_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidencias.id", ondelete="RESTRICT"), index=True
    )
    reportante_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    departamento_id: Mapped[UUID] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    clave_idempotencia: Mapped[UUID]
    hash_solicitud: Mapped[str] = mapped_column(Text)
    responsable_usuario_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    responsable_proveedor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    proveedor_nombre: Mapped[str | None] = mapped_column(Text)
    correo_proveedor: Mapped[str | None] = mapped_column(Text)
    plazo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    nota: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActualizacionIncidencia(Base):
    """Avance, costo o cambio de estado de una incidencia (CON-56)."""

    __tablename__ = "incidencias_actualizaciones"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('COMENTARIO','CAMBIO_ESTADO','COSTO')", name="ck_actualizacion_tipo"
        ),
        CheckConstraint("monto IS NULL OR monto >= 0", name="ck_actualizacion_monto"),
        CheckConstraint(
            "estado_nuevo IS NULL OR estado_nuevo IN "
            "('REGISTRADO','ASIGNADO','EN_PROCESO','RESUELTO','CERRADO','RECHAZADO')",
            name="ck_actualizacion_estado",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    incidencia_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidencias.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    tipo: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    publico: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    repuesto: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estado_anterior: Mapped[str | None] = mapped_column(Text)
    estado_nuevo: Mapped[str | None] = mapped_column(Text)
    evidencia: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    evidencia_mime: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def tiene_evidencia(self) -> bool:
        return self.evidencia_mime is not None
