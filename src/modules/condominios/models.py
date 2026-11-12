"""Modelos ORM de Condominios y Departamentos."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
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
    monto_mora_diario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    politica_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
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
    edificios: Mapped[list["Edificio"]] = relationship(
        "Edificio", back_populates="condominio", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("moneda IN ('PEN', 'USD')", name="ck_condominio_moneda"),
        CheckConstraint(
            "regla_mora_tipo IN ('MONTO_DIARIO', 'MONTO_FIJO', 'PORCENTAJE_SALDO')",
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
            "AND tasa_mora_porcentaje IS NULL AND monto_mora_diario IS NULL) "
            "OR (regla_mora_tipo = 'PORCENTAJE_SALDO' "
            "AND tasa_mora_porcentaje IS NOT NULL "
            "AND monto_mora_fijo IS NULL AND monto_mora_diario IS NULL) "
            "OR (regla_mora_tipo = 'MONTO_DIARIO' AND monto_mora_diario > 0 "
            "AND monto_mora_diario IS NOT NULL AND monto_mora_fijo IS NULL "
            "AND tasa_mora_porcentaje IS NULL)",
            name="ck_condominio_configuracion_mora",
        ),
        CheckConstraint("politica_version > 0", name="ck_condominio_politica_version"),
    )


class Edificio(Base):
    __tablename__ = "edificios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="CASCADE"),
        nullable=False,
    )
    nombre_bloque: Mapped[str] = mapped_column(String(100), nullable=False)
    total_pisos: Mapped[int] = mapped_column(Integer, nullable=False)
    condominio: Mapped["Condominio"] = relationship(back_populates="edificios")
    departamentos: Mapped[list["Departamento"]] = relationship(
        back_populates="edificio", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("condominio_id", "nombre_bloque", name="uq_edificio_condominio_bloque"),
        CheckConstraint("total_pisos >= 1", name="ck_edificio_pisos"),
        Index("idx_edificios_condominio", "condominio_id"),
        Index(
            "uq_edificio_nombre_normalizado",
            "condominio_id",
            func.lower(func.btrim(nombre_bloque)),
            unique=True,
        ),
    )


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edificio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("edificios.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    piso: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    coeficiente_participacion: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    saldo_a_favor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estado_financiero: Mapped[str] = mapped_column(String(20), nullable=False, default="AL_DIA")
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    responsable_pago_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "usuario_departamentos.id", name="fk_departamento_responsable_pago", ondelete="SET NULL"
        ),
        nullable=True,
    )
    condiciones_pago_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    # Relaciones
    edificio: Mapped["Edificio"] = relationship(back_populates="departamentos")

    __table_args__ = (
        UniqueConstraint("edificio_id", "numero", name="uq_edificio_departamento"),
        CheckConstraint("condiciones_pago_version > 0", name="ck_departamento_condiciones_version"),
        Index("idx_departamentos_edificio", "edificio_id"),
        Index(
            "uq_departamento_numero_normalizado",
            "edificio_id",
            func.upper(func.btrim(numero)),
            unique=True,
        ),
        CheckConstraint("piso >= 1", name="ck_departamento_piso"),
        CheckConstraint("coeficiente_participacion > 0.0000", name="ck_departamento_coeficiente"),
        CheckConstraint(
            "coeficiente_participacion <= 100.0000", name="ck_departamento_coeficiente_maximo"
        ),
        CheckConstraint("saldo_a_favor >= 0.00", name="ck_departamento_saldo_favor"),
        CheckConstraint(
            "estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA')",
            name="ck_departamento_estado_financiero",
        ),
    )
