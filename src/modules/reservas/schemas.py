"""Esquemas Pydantic v2 para el Dominio de Reservas (Brandon - PROC-04).

Cumple estrictamente con las especificaciones de OpenAPI 3.1 y SDD.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.modules.reservas.areas.schemas import AreaComunDTO as AreaComunDTO


class CrearReservaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    zona_horaria: Literal["America/Lima", "UTC"] = "America/Lima"
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
        description="Indica si la cancelación es forzada por un administrador de la Junta",
    )


class CancelarReservaResponse(BaseModel):
    id: uuid.UUID
    estado: str = "CANCELADA"
    mensaje: str
    fecha_cancelacion: datetime
    ajuste_economico: dict = Field(
        default_factory=lambda: {
            "estado": "NO_APLICA",
            "monto": "0.00",
            "referencia": None,
        }
    )


class ErrorResponse(BaseModel):
    error_code: str
    mensaje: str
    detalles: Optional[Dict[str, Any]] = None
