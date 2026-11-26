"""Persistencia de excepciones, decisiones y evidencia autorizada (CON-86)."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Excepcion(Base):
    __tablename__ = "excepciones"
    __table_args__ = (UniqueConstraint("alerta_id", name="uq_excepcion_alerta"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    alerta_id: Mapped[UUID]
    notificacion_id: Mapped[UUID | None] = mapped_column(nullable=True)
    condominio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=True
    )
    origen: Mapped[str] = mapped_column(Text)
    operacion_id: Mapped[str] = mapped_column(Text)
    causa: Mapped[str] = mapped_column(Text)
    prioridad: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, default="ABIERTA")
    referencia_correlacion: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResolucionExcepcion(Base):
    __tablename__ = "excepciones_resoluciones"
    __table_args__ = (
        UniqueConstraint("excepcion_id", "clave_idempotencia", name="uq_resolucion_excepcion"),
        Index(
            "uq_excepcion_job_reintento",
            "excepcion_id",
            unique=True,
            postgresql_where=text("accion = 'REINTENTAR_JOB' AND nombre_job IS NOT NULL"),
        ),
        Index(
            "uq_excepcion_job_activo",
            "nombre_job",
            unique=True,
            postgresql_where=text("resultado_job IN ('EN_COLA', 'EN_CURSO')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    excepcion_id: Mapped[UUID] = mapped_column(
        ForeignKey("excepciones.id", ondelete="RESTRICT"), index=True
    )
    accion: Mapped[str] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    efecto: Mapped[dict[str, Any]] = mapped_column(JSONB)
    clave_idempotencia: Mapped[UUID] = mapped_column()
    huella: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    nombre_job: Mapped[str | None] = mapped_column(Text)
    resultado_job: Mapped[str | None] = mapped_column(Text)
    inicio_job: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fin_job: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenciaExcepcion(Base):
    __tablename__ = "excepciones_evidencias"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    excepcion_id: Mapped[UUID] = mapped_column(
        ForeignKey("excepciones.id", ondelete="RESTRICT"), index=True
    )
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
