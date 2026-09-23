"""Esquemas Pydantic para el Dominio de Pagos, Conciliación y Moras (Tarqui - PROC-02).

Alineados formalmente con OpenAPI 3.1: specs/03-contracts/openapi/condomanager.openapi.yaml
"""

from datetime import date
from decimal import Decimal
from typing import Optional
import uuid
from pydantic import BaseModel, Field


class ReportarPagoRequest(BaseModel):
    departamento_id: uuid.UUID
    banco: str = Field(..., json_schema_extra={"example": "YAPE"})
    numero_operacion: str = Field(..., min_length=4, max_length=50, json_schema_extra={"example": "098412"})
    fecha_operacion: date = Field(..., json_schema_extra={"example": "2026-10-15"})
    monto: Decimal = Field(..., gt=Decimal("0.00"), json_schema_extra={"example": "150.00"})
    url_voucher: str = Field(..., json_schema_extra={"example": "https://s3.local/vouchers/voucher_101.jpg"})


class ComprobanteRecibidoResponse(BaseModel):
    comprobante_id: uuid.UUID
    estado: str = "EN_REVISION"
    mensaje: str = "Comprobante recibido. En proceso de conciliación por la Junta Directiva."
    idempotency_hash: str


class ConciliarPagoRequest(BaseModel):
    decision: str = Field(..., pattern=r"^(APROBADO|RECHAZADO|OBSERVADO)$", json_schema_extra={"example": "APROBADO"})
    motivo_rechazo: Optional[str] = None
    notas_internas: Optional[str] = None


class ConciliacionResultResponse(BaseModel):
    comprobante_id: uuid.UUID
    estado_final: str
    monto_imputado: Decimal
    nuevo_saldo_departamento: Decimal
    saldo_a_favor_generado: Decimal
    departamento_habilitado_reservas: bool


class EvaluarMorasRequest(BaseModel):
    condominio_id: uuid.UUID
    fecha_corte: date = Field(default_factory=date.today)


class EvaluarMorasResponse(BaseModel):
    cuotas_evaluadas: int
    moras_aplicadas: int
    cuotas_postergadas_por_revision: int
    monto_total_moras: Decimal
