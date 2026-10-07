"""Esquemas Pydantic v2 para el Dominio de Condominios y Departamentos.

Define el contrato de alta de condominio con la configuración de mora del modelo `condominios`
(specs/03-data-models/domain-entities.md), usando precisión decimal estricta (ADR-002, Zero-Float).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.shared.decimal_types import redondear_moneda


class MonedaEnum(str, Enum):
    PEN = "PEN"
    USD = "USD"


class ReglaMoraEnum(str, Enum):
    MONTO_FIJO = "MONTO_FIJO"
    PORCENTAJE_SALDO = "PORCENTAJE_SALDO"


class CrearCondominioRequest(BaseModel):
    nombre: str = Field(
        ..., min_length=3, max_length=150, json_schema_extra={"example": "Villa Bonita 3"}
    )
    direccion: str = Field(
        ...,
        min_length=5,
        max_length=300,
        json_schema_extra={"example": "Av. Los Rosales 245, Lima"},
    )
    moneda: MonedaEnum = Field(
        default=MonedaEnum.PEN, description="Moneda de la contabilidad del condominio."
    )
    regla_mora_tipo: ReglaMoraEnum = Field(
        default=ReglaMoraEnum.MONTO_FIJO,
        description="Estrategia de cálculo de mora del condominio.",
    )
    monto_mora_fijo: Decimal | None = Field(
        default=Decimal("20.00"),
        gt=Decimal("0.00"),
        le=Decimal("9999999999.99"),
        max_digits=12,
        decimal_places=2,
        description="Cargo fijo de mora por cuota vencida (aplica con regla MONTO_FIJO).",
        json_schema_extra={"example": "20.00"},
    )
    tasa_mora_porcentaje: Decimal | None = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0.0000"),
        le=Decimal("100.0000"),
        max_digits=6,
        decimal_places=4,
        description="Porcentaje sobre la deuda aplicado con regla PORCENTAJE_SALDO.",
        json_schema_extra={"example": "2.5000"},
    )
    dias_corte: int = Field(
        default=20,
        ge=1,
        le=28,
        description="Día del mes de corte de mora (validación CHECK del modelo).",
    )
    dias_gracia: int = Field(
        default=2,
        ge=0,
        description="Días de gracia posteriores al vencimiento antes de aplicar mora.",
    )

    def monto_normalizado(self) -> Decimal | None:
        """Retorna el monto fijo de mora redondeado a 2 decimales (ROUND_HALF_UP)."""
        if self.monto_mora_fijo is None:
            return None
        return redondear_moneda(self.monto_mora_fijo)


class CondominioDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    direccion: str
    moneda: MonedaEnum
    regla_mora_tipo: ReglaMoraEnum
    monto_mora_fijo: Decimal | None = None
    tasa_mora_porcentaje: Decimal | None = None
    dias_corte: int
    dias_gracia: int
    creado_en: datetime = Field(default_factory=lambda: datetime.now(UTC))
