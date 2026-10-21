"""Contrato de configuración: dinero como cadena y horas locales HH:MM."""

from datetime import time
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

PATRON_HORA = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"


class ConfigurarAreaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=4000)
    edificio_id: UUID | None = None
    aforo_maximo: int = Field(strict=True, ge=1, le=2147483647)
    costo_reserva: str = Field(pattern=r"^[0-9]{1,10}(?:\.[0-9]{1,2})?$", max_length=13)
    hora_apertura: str = Field(pattern=PATRON_HORA)
    hora_cierre: str = Field(pattern=PATRON_HORA)
    tiempo_maximo_horas: int = Field(strict=True, ge=1, le=24)

    @model_validator(mode="after")
    def intervalo(self):
        if self.hora_cierre <= self.hora_apertura:
            raise ValueError("El cierre debe ser posterior a la apertura en el mismo día.")
        return self

    def datos_orm(self):
        datos = self.model_dump()
        datos["costo_reserva"] = Decimal(self.costo_reserva).quantize(Decimal("0.01"))
        datos["hora_apertura"] = time.fromisoformat(self.hora_apertura)
        datos["hora_cierre"] = time.fromisoformat(self.hora_cierre)
        return datos


class EstadoAreaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    esta_activa: bool = Field(strict=True)


class AreaComunDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    edificio_id: UUID | None = None
    edificio_nombre: str | None = None
    nombre: str
    descripcion: str | None = None
    aforo_maximo: int = Field(gt=0)
    costo_reserva: Decimal = Field(ge=Decimal("0.00"))
    tiempo_maximo_horas: int = Field(default=4, ge=1)
    esta_activa: bool = True
    hora_apertura: str = Field(default="00:00", pattern=PATRON_HORA)
    hora_cierre: str = Field(default="23:59", pattern=PATRON_HORA)
    moneda: Literal["PEN", "USD"] = "PEN"
    zona_horaria: Literal["America/Lima"] = "America/Lima"

    @field_serializer("costo_reserva", when_used="json")
    def serializar_costo(self, value: Decimal) -> str:
        return format(value, ".2f")
