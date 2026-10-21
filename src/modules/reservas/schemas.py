"""Esquemas Pydantic v2 para el Dominio de Reservas (Brandon - PROC-04).

Cumple estrictamente con las especificaciones de OpenAPI 3.1 y SDD.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.modules.reservas.areas.schemas import AreaComunDTO as AreaComunDTO


class HorarioOcupado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hora_inicio: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]:00$")
    hora_fin: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]:00$")


class CrearReservaRequest(BaseModel):
    condominio_id: uuid.UUID
    area_id: uuid.UUID
    departamento_id: uuid.UUID
    fecha_reserva: date
    hora_inicio: time
    hora_fin: time


class ReservaResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condominio_id: uuid.UUID
    area_id: uuid.UUID
    area_nombre: Optional[str] = None
    departamento_id: uuid.UUID
    fecha_reserva: date
    hora_inicio: time
    hora_fin: time
    costo_reserva: Decimal
    moneda: Literal["PEN", "USD"] = "PEN"
    estado: str  # SOLICITADA, CONFIRMADA, RECHAZADA, CANCELADA, COMPLETADA
    creado_en: datetime


class CancelarReservaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(
        default="Cancelación voluntaria por residente",
        min_length=1,
        max_length=500,
        description="Motivo explicativo de la cancelación",
    )
    es_admin: bool = Field(
        default=False,
        description="Compatibilidad histórica: se ignora; el permiso procede de la sesión.",
    )

    @field_validator("motivo")
    @classmethod
    def normalizar_motivo(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Indique un motivo de cancelación.")
        return value


class AjusteCancelacion(BaseModel):
    estado: Literal["NO_APLICA", "PENDIENTE", "APLICADO"] = "NO_APLICA"
    monto: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    referencia: uuid.UUID | None = None


class CancelarReservaResponse(BaseModel):
    id: uuid.UUID
    estado: str = "CANCELADA"
    mensaje: str
    fecha_cancelacion: datetime
    ajuste_economico: AjusteCancelacion = Field(default_factory=AjusteCancelacion)


class ErrorResponse(BaseModel):
    error_code: str
    mensaje: str
    detalles: Optional[Dict[str, Any]] = None
