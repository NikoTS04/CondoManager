"""Cargos publicados e imputación dirigida; independientes de la cuota mensual."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.shared.decimal_types import Decimal


class RepartoIncidencia(Base):
    __tablename__ = "repartos_incidencia"
    __table_args__ = (
        UniqueConstraint("actualizacion_id", name="uq_reparto_costo"),
        UniqueConstraint("condominio_id", "clave_idempotencia", name="uq_reparto_clave"),
        CheckConstraint("monto > 0", name="ck_reparto_monto"),
        CheckConstraint("metodo IN ('EQUITATIVA','POR_ALICUOTA')", name="ck_reparto_metodo"),
        CheckConstraint("alcance IN ('TODOS','SELECCIONADOS')", name="ck_reparto_alcance"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id"), index=True)
    incidencia_id: Mapped[UUID] = mapped_column(ForeignKey("incidencias.id"))
    actualizacion_id: Mapped[UUID] = mapped_column(ForeignKey("incidencias_actualizaciones.id"))
    clave_idempotencia: Mapped[UUID]
    hash_solicitud: Mapped[str] = mapped_column(String(64))
    concepto: Mapped[str] = mapped_column(String(200))
    motivo: Mapped[str] = mapped_column(String(500))
    alcance: Mapped[str] = mapped_column(String(20))
    metodo: Mapped[str] = mapped_column(String(20))
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    instantanea: Mapped[dict] = mapped_column(JSONB)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CargoIncidencia(Base):
    __tablename__ = "cargos_incidencia"
    __table_args__ = (
        UniqueConstraint("reparto_id", "departamento_id", name="uq_cargo_reparto_unidad"),
        CheckConstraint("monto >= 0 AND pagado BETWEEN 0 AND monto", name="ck_cargo_importes"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reparto_id: Mapped[UUID] = mapped_column(ForeignKey("repartos_incidencia.id"))
    departamento_id: Mapped[UUID] = mapped_column(ForeignKey("departamentos.id"), index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pagado: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), server_default="0"
    )


class DestinoPagoIncidencia(Base):
    __tablename__ = "destinos_pago_incidencia"
    __table_args__ = (CheckConstraint("monto > 0", name="ck_destino_incidencia_monto"),)

    comprobante_id: Mapped[UUID] = mapped_column(
        ForeignKey("comprobantes_pago.id"), primary_key=True
    )
    cargo_id: Mapped[UUID] = mapped_column(ForeignKey("cargos_incidencia.id"), primary_key=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
