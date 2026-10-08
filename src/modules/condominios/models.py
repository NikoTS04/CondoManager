"""Modelos ORM de Condominios y Departamentos."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class Condominio(Base):
    __tablename__ = "condominios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str] = mapped_column(Text, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    regla_mora_tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="MONTO_FIJO")
    monto_mora_fijo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tasa_mora_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    dia_vencimiento: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dias_gracia: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relaciones
    departamentos: Mapped[list["Departamento"]] = relationship(
        "Departamento", back_populates="condominio", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("moneda IN ('PEN', 'USD')", name="ck_condominio_moneda"),
        CheckConstraint(
            "regla_mora_tipo IN ('MONTO_FIJO', 'PORCENTAJE_SALDO')",
            name="ck_condominio_regla_mora",
        ),
        CheckConstraint(
            "dia_vencimiento BETWEEN 1 AND 28",
            name="ck_condominio_dia_vencimiento",
        ),
        CheckConstraint("dias_gracia BETWEEN 0 AND 30", name="ck_condominio_dias_gracia"),
        CheckConstraint(
            "(regla_mora_tipo = 'MONTO_FIJO' "
            "AND monto_mora_fijo IS NOT NULL "
            "AND tasa_mora_porcentaje IS NULL) "
            "OR (regla_mora_tipo = 'PORCENTAJE_SALDO' "
            "AND tasa_mora_porcentaje IS NOT NULL "
            "AND monto_mora_fijo IS NULL)",
            name="ck_condominio_configuracion_mora",
        ),
    )


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="CASCADE"),
        nullable=False,
    )
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    piso: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    coeficiente_participacion: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    saldo_a_favor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estado_financiero: Mapped[str] = mapped_column(String(20), nullable=False, default="AL_DIA")

    # Relaciones
    condominio: Mapped["Condominio"] = relationship("Condominio", back_populates="departamentos")

    __table_args__ = (
        UniqueConstraint("condominio_id", "numero", name="uq_condominio_departamento"),
        CheckConstraint("piso >= 1", name="ck_departamento_piso"),
        CheckConstraint("coeficiente_participacion > 0.0000", name="ck_departamento_coeficiente"),
        CheckConstraint("saldo_a_favor >= 0.00", name="ck_departamento_saldo_favor"),
        CheckConstraint(
            "estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA')",
            name="ck_departamento_estado_financiero",
        ),
    )
