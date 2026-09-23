"""Esquemas Pydantic para el Dominio de Cuotas (Anderson - PROC-01).

Alineados formalmente con OpenAPI 3.1: specs/03-contracts/openapi/condomanager.openapi.yaml
"""

from datetime import date, datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, Field


class EmitirLoteCuotasRequest(BaseModel):
    condominio_id: uuid.UUID = Field(..., description="ID del condominio")
    periodo: str = Field(..., pattern=r"^[0-9]{4}-[0-9]{2}$", json_schema_extra={"example": "2026-10"})
    presupuesto_total: Decimal = Field(..., gt=Decimal("0.00"), json_schema_extra={"example": "20000.00"})
    fecha_vencimiento: date = Field(..., json_schema_extra={"example": "2026-10-20"})


class CuotaDetalleDTO(BaseModel):
    cuota_id: uuid.UUID
    departamento_numero: str
    monto_ordinario: Decimal
    monto_descuento_saldo_favor: Decimal
    monto_total_exigible: Decimal
    estado: str


class EmitirLoteCuotasResponse(BaseModel):
    lote_id: uuid.UUID
    periodo: str
    total_cuotas_emitidas: int
    monto_total_facturado: Decimal
    cuotas_cubiertas_saldo_favor: int
    fecha_emision: datetime
    fecha_vencimiento: date
