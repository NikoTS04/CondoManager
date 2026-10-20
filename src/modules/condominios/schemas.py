"""Contratos Pydantic de la historia CON-2."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Moneda(str, Enum):
    PEN = "PEN"
    USD = "USD"


class ReglaMoraTipo(str, Enum):
    MONTO_FIJO = "MONTO_FIJO"
    PORCENTAJE_SALDO = "PORCENTAJE_SALDO"


class CrearCondominioRequest(BaseModel):
    """Datos que un SUPERADMIN puede establecer durante el alta."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=150)
    direccion: str = Field(min_length=1, max_length=500)
    moneda: Moneda
    regla_mora_tipo: ReglaMoraTipo
    monto_mora_fijo: Decimal | None = Field(
        default=None, ge=Decimal("0.00"), max_digits=12, decimal_places=2
    )
    tasa_mora_porcentaje: Decimal | None = Field(
        default=None,
        ge=Decimal("0.0000"),
        le=Decimal("100.0000"),
        max_digits=7,
        decimal_places=4,
    )
    dia_vencimiento: int = Field(ge=1, le=28)
    dias_gracia: int = Field(ge=0, le=30)

    @field_validator("nombre", "direccion")
    @classmethod
    def normalizar_texto_obligatorio(cls, value: str) -> str:
        normalizado = value.strip()
        if not normalizado:
            raise ValueError("El valor no puede quedar vacío.")
        return normalizado

    @field_validator("monto_mora_fijo", "tasa_mora_porcentaje", mode="before")
    @classmethod
    def exigir_cadena_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, str):
            raise ValueError("Los valores decimales deben enviarse como cadenas.")
        return value

    @model_validator(mode="after")
    def validar_configuracion_mora(self) -> "CrearCondominioRequest":
        if self.regla_mora_tipo is ReglaMoraTipo.MONTO_FIJO:
            if self.monto_mora_fijo is None or self.tasa_mora_porcentaje is not None:
                raise ValueError("MONTO_FIJO exige monto_mora_fijo y prohíbe tasa_mora_porcentaje.")
        elif self.tasa_mora_porcentaje is None or self.monto_mora_fijo is not None:
            raise ValueError(
                "PORCENTAJE_SALDO exige tasa_mora_porcentaje y prohíbe monto_mora_fijo."
            )
        return self


class CondominioResponse(BaseModel):
    """Representación pública persistida del condominio."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    direccion: str
    moneda: Moneda
    regla_mora_tipo: ReglaMoraTipo
    monto_mora_fijo: Decimal | None
    tasa_mora_porcentaje: Decimal | None
    dia_vencimiento: int
    dias_gracia: int
    activo: bool
    creado_en: datetime
