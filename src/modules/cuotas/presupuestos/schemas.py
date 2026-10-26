"""Contratos Pydantic del presupuesto mensual de CON-9."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.modules.cuotas.prorrateo_schemas import ItemPresupuesto

PERIODO_PATTERN = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
MONTO_PATTERN = r"^(?:0|[1-9][0-9]{0,9})\.[0-9]{2}$"


class MonedaPresupuesto(str, Enum):
    PEN = "PEN"
    USD = "USD"


class EstadoPresupuesto(str, Enum):
    BORRADOR = "BORRADOR"
    APROBADO = "APROBADO"


class DatosPresupuestoRequest(BaseModel):
    """Campos editables comunes a creación y reemplazo de un borrador."""

    model_config = ConfigDict(extra="forbid")

    periodo: str = Field(pattern=PERIODO_PATTERN)
    moneda: MonedaPresupuesto
    monto_total: Decimal | None = Field(
        default=None, ge=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
    )
    fecha_vencimiento: date
    items: list[ItemPresupuesto] | None = Field(default=None, min_length=1, max_length=500)
    version_esperada: int | None = Field(default=None, ge=1, strict=True)

    @field_validator("monto_total", mode="before")
    @classmethod
    def exigir_monto_como_cadena(cls, value: object) -> object:
        if not isinstance(value, str) or re.fullmatch(MONTO_PATTERN, value) is None:
            raise ValueError(
                "El monto debe enviarse como una cadena decimal positiva con dos dígitos."
            )
        return value

    @model_validator(mode="after")
    def validar_vencimiento_en_periodo(self) -> "DatosPresupuestoRequest":
        if self.fecha_vencimiento.strftime("%Y-%m") != self.periodo:
            raise ValueError("La fecha de vencimiento debe pertenecer al periodo registrado.")
        if self.items is None:
            if self.monto_total is None or self.monto_total <= 0:
                raise ValueError("Sin detalle se requiere un total positivo.")
        else:
            if len({i.id for i in self.items}) != len(self.items):
                raise ValueError("Los identificadores de ítems no pueden repetirse.")
            calculado = sum((i.monto_periodo * (-1 if i.tipo_movimiento == "ABONO" else 1) for i in self.items), Decimal("0.00"))
            if not Decimal("0.00") <= calculado <= Decimal("9999999999.99"):
                raise ValueError("Total distribuible fuera de rango.")
            if self.monto_total is not None and self.monto_total != calculado:
                raise ValueError("El total de control no coincide con los ítems.")
            self.monto_total = calculado
        return self


class CrearPresupuestoRequest(DatosPresupuestoRequest):
    condominio_id: UUID


class ActualizarPresupuestoRequest(DatosPresupuestoRequest):
    pass


class PresupuestoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    periodo: str
    moneda: MonedaPresupuesto
    monto_total: Decimal
    fecha_vencimiento: date
    estado: EstadoPresupuesto
    creado_por: str
    creado_en: datetime
    aprobado_por: str | None
    aprobado_en: datetime | None
    actualizado_en: datetime
    version: int = 1
    items: list[ItemPresupuesto] | None = None
