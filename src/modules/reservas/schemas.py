"""Esquemas Pydantic v2 para el Dominio de Reservas (Brandon - PROC-04).

Cumple estrictamente con las especificaciones de OpenAPI 3.1 y SDD.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class AreaComunDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    condominio_id: uuid.UUID
    nombre: str
    descripcion: Optional[str] = None
    aforo_maximo: int = Field(gt=0, description="Aforo máximo de personas permitidas")
    costo_reserva: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Costo por turno de uso en PEN")
    esta_activa: bool = True


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
    detalles: Optional[Dict[str, Any]] = None
