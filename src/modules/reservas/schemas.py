"""Esquemas Pydantic v2 para el Dominio de Reservas (Brandon - PROC-04).

Cumple estrictamente con las especificaciones de OpenAPI 3.1 y SDD.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AreaComunDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    condominio_id: uuid.UUID
    nombre: str
    descripcion: str | None = None
    aforo_maximo: int = Field(gt=0, description="Aforo máximo de personas permitidas")
    costo_reserva: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Costo por turno de uso en PEN")
    esta_activa: bool = True


class CrearAreaRequest(BaseModel):
    condominio_id: uuid.UUID
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre del área común")
    descripcion: str | None = Field(default=None, max_length=500)
    aforo_maximo: int = Field(..., gt=0, description="Aforo máximo de personas permitidas")
    costo_reserva: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        le=Decimal("9999999999.99"),
        max_digits=12,
        decimal_places=2,
        description="Costo por turno de uso en PEN",
    )
    esta_activa: bool = Field(default=True, description="Indica si el área queda disponible para reservar")


class CrearReservaRequest(BaseModel):
    condominio_id: uuid.UUID | None = Field(
        default=None,
        description="Informativo. La fuente de verdad es el condominio del área común seleccionada.",
    )
    area_id: uuid.UUID
    departamento_id: uuid.UUID | str = Field(
        ...,
        description="UUID del departamento o su número (ej. \"402\"). El router lo normaliza a UUID.",
    )
    fecha_reserva: date
    hora_inicio: time
    hora_fin: time


class ReservaResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condominio_id: uuid.UUID
    area_id: uuid.UUID
    area_nombre: str | None = None
    departamento_id: uuid.UUID
    fecha_reserva: date
    hora_inicio: time
    hora_fin: time
    costo_reserva: Decimal
    estado: str  # SOLICITADA, CONFIRMADA, RECHAZADA, CANCELADA, COMPLETADA
    creado_en: datetime


class CancelarReservaRequest(BaseModel):
    motivo: str = Field(
        default="Cancelación voluntaria por residente",
        description="Motivo explicativo de la cancelación"
    )
    es_admin: bool = Field(
        default=False,
        description="Indica si la cancelación es forzada por un administrador de la Junta"
    )


class CancelarReservaResponse(BaseModel):
    id: uuid.UUID
    estado: str = "CANCELADA"
    mensaje: str
    fecha_cancelacion: datetime


class ErrorResponse(BaseModel):
    error_code: str
    mensaje: str
    detalles: dict[str, Any] | None = None
