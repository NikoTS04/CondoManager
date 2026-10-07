"""Modelos ORM de Condominios y Departamentos."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str] = mapped_column(Text, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    regla_mora_tipo: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MONTO_FIJO"
    )
    monto_mora_fijo: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=True, default=Decimal("20.00")
    )
    tasa_mora_porcentaje: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=True, default=Decimal("0.0000")
    )
    dias_corte: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=20)
    dias_gracia: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
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
        CheckConstraint("dias_corte BETWEEN 1 AND 28", name="ck_condominio_dias_corte"),
        CheckConstraint("dias_gracia >= 0", name="ck_condominio_dias_gracia"),
    )


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="CASCADE"),
        nullable=False,
    )
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    piso: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    coeficiente_participacion: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False
    )
    saldo_a_favor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estado_financiero: Mapped[str] = mapped_column(
        String(20), nullable=False, default="AL_DIA"
    )

    # Relaciones
    condominio: Mapped["Condominio"] = relationship(
        "Condominio", back_populates="departamentos"
    )

    __table_args__ = (
        UniqueConstraint("condominio_id", "numero", name="uq_condominio_departamento"),
        CheckConstraint("piso >= 1", name="ck_departamento_piso"),
        CheckConstraint(
            "coeficiente_participacion > 0.0000", name="ck_departamento_coeficiente"
        ),
        CheckConstraint("saldo_a_favor >= 0.00", name="ck_departamento_saldo_favor"),
        CheckConstraint(
            "estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA')",
            name="ck_departamento_estado_financiero",
        ),
    )
